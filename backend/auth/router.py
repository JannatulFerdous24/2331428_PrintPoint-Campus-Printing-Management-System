"""
HTTP endpoints for authentication (/api/auth/...) and the user's own account
(/api/users/me...). Business rules live in auth/service.py.

The refresh token travels ONLY in this cookie:
    pp_refresh  httpOnly (JavaScript cannot read it), Secure on HTTPS,
                SameSite=Lax, Path=/api/auth (not sent to any other endpoint)
"""

from typing import Optional

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from audit import log_event
from auth import service
from auth.dependencies import get_current_user
from auth.schemas import (
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    SessionRead,
    SignupRequest,
    TokenResponse,
    UserRead,
)
from auth.tokens import decode_access_token
from config import get_settings
from database import get_session
from models import User

REFRESH_COOKIE = "pp_refresh"
REFRESH_COOKIE_PATH = "/api/auth"

router = APIRouter(prefix="/api/auth", tags=["auth"])
users_router = APIRouter(prefix="/api/users", tags=["account"])
_optional_bearer = HTTPBearer(auto_error=False)


# ----------------------------------------------------------------- helpers

def require_ajax_header(request: Request) -> None:
    """CSRF protection for cookie-based endpoints (/refresh, /logout).

    Browsers only let JavaScript add a custom header like X-Requested-With to a
    request for another site after a CORS check, which our CORS settings deny.
    So a malicious site cannot make your browser call /refresh or /logout.
    """
    if request.headers.get("x-requested-with") != "XMLHttpRequest":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Missing X-Requested-With header")


def _set_refresh_cookie(response: Response, raw_token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=raw_token,
        max_age=settings.refresh_token_days * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=REFRESH_COOKIE, path=REFRESH_COOKIE_PATH,
        httponly=True, secure=settings.cookie_secure, samesite="lax",
    )


def _token_response(response: Response, user: User, access: str, expires_in: int, raw: str) -> TokenResponse:
    _set_refresh_cookie(response, raw)
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(access_token=access, expires_in=expires_in, user=UserRead.model_validate(user))


# ---------------------------------------------------------------- endpoints

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def signup(data: SignupRequest, request: Request, response: Response,
           session: Session = Depends(get_session)):
    user, access, expires_in, raw = service.signup(session, data, request)
    return _token_response(response, user, access, expires_in, raw)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, request: Request, response: Response,
          session: Session = Depends(get_session)):
    user, access, expires_in, raw = service.login(session, data, request)
    return _token_response(response, user, access, expires_in, raw)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(require_ajax_header)],
             responses={204: {"description": "No refresh cookie sent: the visitor has no session"}})
def refresh(request: Request, response: Response,
            pp_refresh: Optional[str] = Cookie(default=None),
            session: Session = Depends(get_session)):
    if not pp_refresh:
        # A visitor who never logged in: nothing to restore. Answer "no session" (204, no token)
        # instead of 401 so the browser does not log an error on every first visit.
        # Any cookie that IS sent but is invalid, expired, revoked or reused still gets 401 below.
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    try:
        user, access, expires_in, raw = service.refresh(session, pp_refresh, request)
    except HTTPException:
        _clear_refresh_cookie(response)
        raise
    return _token_response(response, user, access, expires_in, raw)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT,
             dependencies=[Depends(require_ajax_header)])
def logout(request: Request, response: Response,
           pp_refresh: Optional[str] = Cookie(default=None),
           credentials: Optional[HTTPAuthorizationCredentials] = Depends(_optional_bearer),
           session: Session = Depends(get_session)):
    # Works even if the access token already expired: the cookie identifies the session.
    session_id = None
    if credentials is not None:
        try:
            session_id = int(decode_access_token(credentials.credentials)["sid"])
        except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
            session_id = None
    service.logout(session, pp_refresh, session_id, request)
    _clear_refresh_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(request: Request, user: User = Depends(get_current_user),
                  session: Session = Depends(get_session)):
    current = getattr(request.state, "session_id", None)
    return [
        SessionRead(
            id=rs.id, ip_address=rs.ip_address, user_agent=rs.user_agent,
            created_at=rs.created_at, last_used_at=rs.last_used_at,
            expires_at=rs.expires_at, current=(rs.id == current),
        )
        for rs in service.list_active_sessions(session, user)
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(session_id: int, request: Request, user: User = Depends(get_current_user),
                   session: Session = Depends(get_session)):
    service.revoke_session(session, user, session_id, request)


@router.post("/sessions/revoke-others")
def revoke_other_sessions(request: Request, user: User = Depends(get_current_user),
                          session: Session = Depends(get_session)):
    current = getattr(request.state, "session_id", None)
    count = service.revoke_other_sessions(session, user, current)
    log_event(session, "session.revoke_others", request=request, actor_id=user.id,
              target_type="user", target_id=user.id, details={"revoked": count})
    session.commit()
    return {"revoked": count}


# ------------------------------------------------------------ own account

@users_router.get("/me", response_model=UserRead)
def get_profile(user: User = Depends(get_current_user)):
    return user


@users_router.patch("/me", response_model=UserRead)
def update_profile(data: ProfileUpdate, request: Request, user: User = Depends(get_current_user),
                   session: Session = Depends(get_session)):
    return service.update_profile(session, user, data, request)


@users_router.post("/me/password")
def change_password(data: PasswordChange, request: Request, user: User = Depends(get_current_user),
                    session: Session = Depends(get_session)):
    current = getattr(request.state, "session_id", None)
    revoked = service.change_password(session, user, data, current, request)
    return {"detail": "Password changed", "other_sessions_revoked": revoked}
