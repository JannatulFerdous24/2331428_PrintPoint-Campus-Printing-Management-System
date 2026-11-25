"""
Tokens.

ACCESS TOKEN (JWT, lives <= 15 minutes, kept in browser memory):
    header.payload.signature
    payload = {sub: user id, role, sid: session id, type: "access", iat, exp, jti}
    The signature is an HMAC-SHA256 of header+payload with JWT_SECRET. Changing any
    character of the payload makes the signature invalid -> 401.

REFRESH TOKEN (random string, lives REFRESH_TOKEN_DAYS, in an httpOnly cookie):
    Only its SHA-256 hash is stored in refresh_sessions.token_hash, so a database
    leak does not reveal usable refresh tokens.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from config import get_settings

ACCESS_TOKEN_TYPE = "access"


def create_access_token(user_id: int, role: str, session_id: int) -> tuple[str, int]:
    """Return (token, lifetime_in_seconds)."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,
        "sid": session_id,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + lifetime,
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> dict:
    """Verify signature, expiry and required claims.

    Raises jwt.ExpiredSignatureError for expired tokens and
    jwt.InvalidTokenError for anything else that is wrong.
    """
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],  # never accept "none" or other algorithms
        options={"require": ["exp", "iat", "sub", "sid", "type"]},
        leeway=10,  # tolerate up to 10 s clock difference between servers
    )
    if payload.get("type") != ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits of randomness


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
