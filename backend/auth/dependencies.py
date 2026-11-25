"""
`get_current_user` - the FastAPI dependency that protects endpoints.

Every protected request goes through these checks, in order:
  1. Is there an "Authorization: Bearer <token>" header?        no  -> 401
  2. Is the JWT signature valid and not tampered with?           no  -> 401
  3. Has the token expired?                                      yes -> 401
  4. Does the user still exist?                                  no  -> 401
  5. Is the user banned?  (read from the DATABASE, not the token) yes -> 403
  6. Is the login session still active (not logged out/revoked)? no  -> 401

Steps 5 and 6 read the database on every request. That is why a ban or a logout
takes effect immediately instead of waiting for the token to expire.
"""

from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from auth.tokens import decode_access_token
from database import get_session
from models import RefreshSession, User

_bearer = HTTPBearer(auto_error=False)


def as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def session_is_active(rs: RefreshSession | None) -> bool:
    return (
        rs is not None
        and rs.revoked_at is None
        and as_utc(rs.expires_at) > datetime.now(timezone.utc)
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Access token expired")
    except jwt.InvalidTokenError:
        raise _unauthorized("Invalid access token")

    try:
        user_id = int(payload["sub"])
        session_id = int(payload["sid"])
    except (TypeError, ValueError):
        raise _unauthorized("Invalid access token")

    user = session.get(User, user_id)
    if user is None:
        raise _unauthorized("Invalid access token")

    if user.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is banned")

    rs = session.get(RefreshSession, session_id)
    if not session_is_active(rs) or rs.user_id != user.id:
        raise _unauthorized("Session has ended. Please log in again.")

    # Make the session id available to endpoints (e.g. to mark "this device").
    request.state.session_id = session_id
    return user
