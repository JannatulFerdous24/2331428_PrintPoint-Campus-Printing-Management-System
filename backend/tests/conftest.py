"""
Shared pytest setup.

This file is loaded by pytest BEFORE any test module, so the environment
variable below is set before `main` / `database` are imported. That means the
app's own engine - including the one used by FastAPI startup (init_db) - points
at a throw-away in-memory SQLite database, never at a real file or Supabase.
"""

import os

# Force (not setdefault): even if a real DATABASE_URL is set in the terminal or
# in backend/.env, tests must never touch it.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ.pop("VERCEL", None)

# Test-only secrets (NOT the real ones from backend/.env, which tests must never use).
os.environ["JWT_SECRET"] = "test-jwt-secret-0123456789-abcdefghijklmnopqrstuvwxyz"
os.environ["PASSWORD_PEPPER"] = "test-pepper-0123456789-abcdefghijklmnopqrstuvwxyz"
os.environ["ACCESS_TOKEN_MINUTES"] = "15"
os.environ["REFRESH_TOKEN_DAYS"] = "7"
os.environ["COOKIE_SECURE"] = "false"  # TestClient talks plain http://testserver
for _name in ("LOGIN_LOCKOUT_THRESHOLD", "LOGIN_LOCKOUT_MINUTES",
              "LOGIN_IP_FAIL_LIMIT", "LOGIN_IP_WINDOW_MINUTES"):
    os.environ.pop(_name, None)

# Tests never talk to the real Supabase Storage bucket: empty values here win over
# backend/.env (load_dotenv does not override existing variables). Document tests
# inject an in-memory storage instead.
for _name in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ[_name] = ""
