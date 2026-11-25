"""
Create a new admin (print-shop staff) account, or promote an existing user.

Signup can only ever create `user` accounts, so this is the secure way to get
the first admin. Run it from YOUR OWN terminal, inside the backend folder:

    .venv\\Scripts\\python.exe scripts\\create_admin.py --email staff@uni.edu --name "Print Staff"

* The password is typed at a hidden prompt (twice) - never on the command line,
  never printed, never stored except as an Argon2 hash.
* It uses DATABASE_URL from backend/.env (make sure that is the database you mean).
* The action is written to the audit log.
"""

import argparse
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

from audit import log_event  # noqa: E402
from auth.security import hash_password, password_problems  # noqa: E402
from database import engine, init_db  # noqa: E402
from models import User, UserRole  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote a PrintPoint admin account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", help="Full name (required when creating a new account)")
    parser.add_argument("--promote-only", action="store_true",
                        help="Only promote an existing user; never create a new one")
    args = parser.parse_args()
    email = args.email.strip().lower()

    init_db()  # SQLite only; no-op on PostgreSQL
    print(f"Database: {engine.dialect.name} ({engine.url.host or engine.url.database})")

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()

        if user is not None:
            if user.role == UserRole.admin:
                print(f"{email} is already an admin. Nothing changed.")
                return 0
            if input(f"Promote existing user {email} to admin? [y/N] ").strip().lower() != "y":
                print("Cancelled.")
                return 1
            user.role = UserRole.admin
            user.updated_at = datetime.now(timezone.utc)
            session.add(user)
            log_event(session, "user.role_change", target_type="user", target_id=user.id,
                      details={"from": "user", "to": "admin", "via": "create_admin.py"})
            session.commit()
            print(f"Promoted {email} to admin (user id {user.id}).")
            return 0

        if args.promote_only:
            print(f"No user with email {email}. Nothing changed.")
            return 1
        if not args.name:
            print("--name is required to create a new admin account.")
            return 1

        password = getpass.getpass("New admin password (hidden): ")
        problems = password_problems(password, email)
        if problems:
            print("Password must have " + ", ".join(problems) + ".")
            return 1
        if getpass.getpass("Repeat password: ") != password:
            print("Passwords do not match.")
            return 1

        user = User(email=email, full_name=args.name.strip(), password_hash=hash_password(password),
                    role=UserRole.admin, password_changed_at=datetime.now(timezone.utc))
        session.add(user)
        session.flush()
        log_event(session, "user.admin_created", target_type="user", target_id=user.id,
                  details={"via": "create_admin.py"})
        session.commit()
        print(f"Created admin {email} (user id {user.id}).")
        return 0


if __name__ == "__main__":
    sys.exit(main())
