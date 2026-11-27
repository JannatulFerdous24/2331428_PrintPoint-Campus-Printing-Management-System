"""
Viva demo: how SALT and PEPPER protect passwords (same steps as backend/auth/security.py).
Uses DEMO values only - never the real PASSWORD_PEPPER, never the database.

    .venv\\Scripts\\python.exe scripts\\demo_salt_pepper.py
"""

import hashlib
import hmac

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

ph = PasswordHasher()  # Argon2id, same as the app
PASSWORD = "MyPassword123"
DEMO_PEPPER = "demo-pepper-for-the-viva-only"
WRONG_PEPPER = "attacker-does-not-know-the-real-pepper"


def pepper(key: str, password: str) -> str:
    # Step 1 (PEPPER): HMAC-SHA256 with a secret key that is NOT stored in the database
    return hmac.new(key.encode(), password.encode(), hashlib.sha256).hexdigest()


def check(stored_hash: str, key: str, password: str) -> bool:
    try:
        return ph.verify(stored_hash, pepper(key, password))
    except VerifyMismatchError:
        return False


# Step 2 (SALT): Argon2 creates a new random salt for every hash and stores it inside the hash
h1 = ph.hash(pepper(DEMO_PEPPER, PASSWORD))
h2 = ph.hash(pepper(DEMO_PEPPER, PASSWORD))

print("Password:", PASSWORD)
print("\n--- SALT ---")
print("Hash 1:", h1)
print("Hash 2:", h2)
print("Salt 1:", h1.split("$")[4])
print("Salt 2:", h2.split("$")[4])
print("Same password -> same hash?", h1 == h2, " (no: a different random salt each time)")

print("\n--- PEPPER ---")
print("Right password + right pepper :", check(h1, DEMO_PEPPER, PASSWORD))
print("Wrong password + right pepper :", check(h1, DEMO_PEPPER, "WrongPass123"))
print("Right password + WRONG pepper :", check(h1, WRONG_PEPPER, PASSWORD),
      " (a stolen database is useless without the pepper)")
