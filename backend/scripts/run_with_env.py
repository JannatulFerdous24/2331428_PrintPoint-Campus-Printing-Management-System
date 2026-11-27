"""
Run one backend command with the settings from a chosen env file (e.g. Production),
instead of backend/.env. Values are loaded into this process only and never printed.

    python scripts/run_with_env.py C:\\path\\to\\prod.env -m alembic upgrade head
    python scripts/run_with_env.py C:\\path\\to\\prod.env scripts/create_admin.py --email ... --name ...

The env file must live OUTSIDE the repository (it contains secrets).
"""

import os
import runpy
import sys
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent.parent


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    env_file = Path(sys.argv[1]).resolve()
    if BACKEND_DIR.parent in env_file.parents:
        sys.exit("SAFETY STOP: keep secret env files outside the repository")
    if not env_file.is_file():
        sys.exit(f"Env file not found: {env_file}")
    values = {k: v for k, v in dotenv_values(env_file).items() if v is not None}
    os.environ.update(values)  # wins over backend/.env (load_dotenv never overrides)
    print(f"Using settings from {env_file.name} ({len(values)} values, not shown)")

    os.chdir(BACKEND_DIR)
    sys.path.insert(0, str(BACKEND_DIR))
    args = sys.argv[2:]
    if args[0] == "-m":
        sys.argv = [args[1], *args[2:]]
        runpy.run_module(args[1], run_name="__main__", alter_sys=True)
    else:
        sys.argv = args
        runpy.run_path(args[0], run_name="__main__")


if __name__ == "__main__":
    main()
