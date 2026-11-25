"""
Password hashing with Argon2id + a server-side pepper.

    stored_hash = argon2id( HMAC-SHA256(PASSWORD_PEPPER, password) )

* Argon2id is slow and memory-hard on purpose, so guessing passwords is expensive.
* Argon2 adds a random salt per user, so equal passwords get different hashes.
* The pepper is a secret that lives only in an environment variable, never in the
  database - a stolen database alone is not enough to start cracking passwords.
"""

import hashlib
import hmac
import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from config import get_settings

_hasher = PasswordHasher()  # argon2id with the library's recommended parameters

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 128


def _pepper(password: str) -> str:
    key = get_settings().password_pepper.encode()
    return hmac.new(key, password.encode("utf-8"), hashlib.sha256).hexdigest()


def hash_password(password: str) -> str:
    return _hasher.hash(_pepper(password))


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return _hasher.verify(stored_hash, _pepper(password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


# Used when the email does not exist, so a login takes about the same time either
# way and attackers cannot discover registered emails by timing the response.
_DUMMY_HASH: str | None = None


def burn_time_for_unknown_user(password: str) -> None:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("dummy-password-for-timing-1")
    verify_password(password, _DUMMY_HASH)


def password_problems(password: str, email: str | None = None) -> list[str]:
    """Return a list of human-readable rule violations (empty list = OK)."""
    problems = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(f"at most {PASSWORD_MAX_LENGTH} characters")
    if not re.search(r"[A-Za-z]", password):
        problems.append("at least one letter")
    if not re.search(r"\d", password):
        problems.append("at least one digit")
    if email and password.strip().lower() == email.strip().lower():
        problems.append("must not be the same as your email")
    return problems
