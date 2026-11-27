"""
Create the instructor demo data: 2 admins (print-shop staff), 3 students, one shared
group with MIXED permissions and a few sample print requests.

* Passwords are random (secrets module) and written ONLY to the file given with
  --out (must be outside the repository). They are never printed.
* Safe: dry run by default; with --execute it STOPS if any demo email already
  exists or the output file already exists. Nothing existing is changed.
* Uses the app's own code (hash_password, crud) so hashing, cost, status
  history and audit entries are exactly what the real app produces.

    .venv\\Scripts\\python.exe scripts\\run_with_env.py <prod.env> scripts\\seed_demo.py --out <file> [--execute]
"""

import argparse
import secrets
import string
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select  # noqa: E402

import crud  # noqa: E402
from audit import log_event  # noqa: E402
from auth.security import hash_password, password_problems, verify_password  # noqa: E402
from database import engine  # noqa: E402
from models import Group, GroupMember, PaymentStatus, PrintRequest, RequestStatus, User, UserRole  # noqa: E402
from schemas import PrintRequestCreate, PrintRequestUpdate  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent

ACCOUNTS = [  # key, email, full name, role
    ("admin1", "demo.admin1@uni.edu", "Demo Staff One", UserRole.admin),
    ("admin2", "demo.admin2@uni.edu", "Demo Staff Two", UserRole.admin),
    ("s1", "demo.student1@uni.edu", "Demo Student One", UserRole.user),
    ("s2", "demo.student2@uni.edu", "Demo Student Two", UserRole.user),
    ("s3", "demo.student3@uni.edu", "Demo Student Three", UserRole.user),
]
GROUP_NAME = "CSE309 Project Team"
# Owner = s1 (all powers). s2 may create + edit (not assign). s3 is view-only.
MEMBERS = {"s2": dict(can_create=True, can_edit=True, can_assign=False),
           "s3": dict(can_create=False, can_edit=False, can_assign=False)}

# owner, in_group, document, pages, copies, type, status path, paid, reject reason
REQUESTS = [
    ("s1", False, "Lab Report 3", 12, 1, "Black & White", [], False, None),
    ("s1", True, "Project Proposal", 8, 4, "Color", ["Processing"], True, None),
    ("s2", True, "Survey Questionnaire", 2, 30, "Black & White", ["Processing", "Ready"], True, None),
    ("s2", False, "Curriculum Vitae", 2, 3, "Color", ["Processing", "Ready", "Collected"], True, None),
    ("s3", False, "Lecture Slides Week 9", 40, 1, "Black & White", ["Rejected"], False,
     "The PDF is password-protected; please upload an unlocked copy"),
    ("s3", False, "Assignment 2", 6, 2, "Black & White", [], False, None),
]


def new_password() -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(16))
        if any(c.isdigit() for c in pw) and any(c.isalpha() for c in pw) and not password_problems(pw):
            return pw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="credentials file, outside the repository")
    ap.add_argument("--execute", action="store_true")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    if REPO in out.parents:
        sys.exit("SAFETY STOP: --out must be outside the repository")
    print(f"Database: {engine.dialect.name} ({engine.url.host})")

    with Session(engine) as session:
        emails = [a[1] for a in ACCOUNTS]
        existing = session.exec(select(User.email).where(User.email.in_(emails))).all()
        print(f"Existing users: {len(session.exec(select(User.id)).all())}; demo emails already present: {len(existing)}")
        print(f"Plan: {len(ACCOUNTS)} accounts, group '{GROUP_NAME}' (+{len(MEMBERS)} members), {len(REQUESTS)} requests")
        if existing:
            sys.exit("SAFETY STOP: demo accounts already exist - nothing changed")
        if out.exists():
            sys.exit("SAFETY STOP: output file already exists - nothing changed")
        if not args.execute:
            print("Dry run only. Add --execute to create.")
            return

        passwords, users = {}, {}
        for key, email, name, role in ACCOUNTS:
            passwords[key] = new_password()
            u = User(email=email, full_name=name, role=role, password_hash=hash_password(passwords[key]))
            session.add(u)
            session.flush()
            users[key] = u
            log_event(session, "user.seed_demo", actor_id=None, target_type="user", target_id=u.id,
                      details={"role": role.value})

        group = Group(name=GROUP_NAME, description="Shared printing for the CSE309 final project team",
                      owner_id=users["s1"].id)
        session.add(group)
        session.flush()
        session.add(GroupMember(group_id=group.id, user_id=users["s1"].id, can_create=True, can_edit=True,
                                can_assign=True, added_by_id=users["s1"].id))
        for key, flags in MEMBERS.items():
            session.add(GroupMember(group_id=group.id, user_id=users[key].id, added_by_id=users["s1"].id, **flags))
        log_event(session, "group.create", actor_id=users["s1"].id, target_type="group", target_id=group.id,
                  details={"name": GROUP_NAME})
        session.commit()

        staff = users["admin1"]
        for owner, in_group, doc, pages, copies, ptype, path, paid, reason in REQUESTS:
            pr = crud.create_print_request(session, PrintRequestCreate(
                student_name=users[owner].full_name, document_name=doc, pages=pages, copies=copies,
                print_type=ptype, group_id=group.id if in_group else None), owner_id=users[owner].id)
            for step in path:
                pr = crud.update_print_request(session, pr, PrintRequestUpdate(
                    status=step, reason=reason if step == "Rejected" else None), actor=staff)
            if paid:
                pr = crud.update_payment_status(session, pr, PaymentStatus.paid, actor=staff)
            if doc == "Project Proposal":  # group owner assigns it to a member
                pr.assignee_id = users["s2"].id
                session.add(pr)
                session.commit()

        with out.open("x", encoding="utf-8") as f:
            f.write("PrintPoint DEMO accounts (Production) - demo data only. Do NOT commit or share publicly.\n")
            f.write("Use in the submission form and the PDF report only, never in the README.\n\n")
            for key, email, name, role in ACCOUNTS:
                label = "admin (Print-Shop Staff)" if role == UserRole.admin else "user (Student)"
                f.write(f"{label:26} {email:26} password: {passwords[key]}\n")
            f.write(f"\nShared group: \"{GROUP_NAME}\"\n")
            f.write("  owner  demo.student1@uni.edu  - all powers: create, edit, assign, rename, delete, manage members\n")
            f.write("  member demo.student2@uni.edu  - can create + edit group requests, cannot assign\n")
            f.write("  member demo.student3@uni.edu  - view only (cannot create, edit or assign)\n")
            f.write("  admins are NOT members (they moderate via the admin dashboard)\n")
        print(f"Created. Credentials written to {out} (not shown)")

        # ---- verification (no secrets printed)
        session.expire_all()
        ok = True
        for key, email, _, role in ACCOUNTS:
            u = session.exec(select(User).where(User.email == email)).one()
            good = u.role == role and not u.is_banned and verify_password(passwords[key], u.password_hash)
            ok &= good
            print(f"  {'OK ' if good else 'BAD'} {email} role={u.role.value} password verifies={good}")
        flags = {m.user_id: (m.can_create, m.can_edit, m.can_assign)
                 for m in session.exec(select(GroupMember).where(GroupMember.group_id == group.id))}
        print("  group members (create, edit, assign):",
              {k: flags[users[k].id] for k in ("s1", "s2", "s3")})
        for pr in session.exec(select(PrintRequest).order_by(PrintRequest.id)):
            print(f"  request #{pr.id} {pr.document_name!r}: {pr.pages}p x{pr.copies} {pr.print_type.value} "
                  f"= Tk {pr.total_cost}, {pr.status.value}, payment {pr.payment_status.value}, "
                  f"group={'yes' if pr.group_id else 'no'}")
        print("VERIFIED" if ok else "VERIFICATION FAILED")


if __name__ == "__main__":
    main()
