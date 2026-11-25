"""
Application settings read from environment variables (backend/.env locally,
Vercel environment variables in the cloud). Secrets never live in code.
"""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv(override=False)

MIN_SECRET_LENGTH = 32
MAX_ACCESS_TOKEN_MINUTES = 15  # course requirement: access token lifetime <= 15 minutes


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    return int(raw) if raw else default


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    password_pepper: str
    jwt_algorithm: str
    access_token_minutes: int
    refresh_token_days: int
    cookie_secure: bool
    # Brute-force protection
    lockout_threshold: int      # wrong passwords in a row before the account locks
    lockout_minutes: int        # how long the lock lasts
    ip_fail_limit: int          # failed logins allowed from one IP ...
    ip_window_minutes: int      # ... within this many minutes


@lru_cache
def get_settings() -> Settings:
    on_vercel = bool(os.getenv("VERCEL"))
    jwt_secret = os.getenv("JWT_SECRET", "").strip()
    pepper = os.getenv("PASSWORD_PEPPER", "").strip()

    for name, value in (("JWT_SECRET", jwt_secret), ("PASSWORD_PEPPER", pepper)):
        if len(value) < MIN_SECRET_LENGTH:
            raise RuntimeError(
                f"{name} is missing or shorter than {MIN_SECRET_LENGTH} characters. "
                "Set it in backend/.env (local) or the Vercel environment variables."
            )

    minutes = _int_env("ACCESS_TOKEN_MINUTES", MAX_ACCESS_TOKEN_MINUTES)
    if not 1 <= minutes <= MAX_ACCESS_TOKEN_MINUTES:
        raise RuntimeError("ACCESS_TOKEN_MINUTES must be between 1 and 15.")

    cookie_secure_raw = os.getenv("COOKIE_SECURE", "").strip().lower()
    # Default: secure cookies on Vercel (HTTPS). Never allow insecure cookies there.
    cookie_secure = True if on_vercel else cookie_secure_raw in ("1", "true", "yes")

    return Settings(
        jwt_secret=jwt_secret,
        password_pepper=pepper,
        jwt_algorithm="HS256",
        access_token_minutes=minutes,
        refresh_token_days=_int_env("REFRESH_TOKEN_DAYS", 7),
        cookie_secure=cookie_secure,
        lockout_threshold=_int_env("LOGIN_LOCKOUT_THRESHOLD", 5),
        lockout_minutes=_int_env("LOGIN_LOCKOUT_MINUTES", 15),
        ip_fail_limit=_int_env("LOGIN_IP_FAIL_LIMIT", 20),
        ip_window_minutes=_int_env("LOGIN_IP_WINDOW_MINUTES", 15),
    )
