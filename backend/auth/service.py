"""
Authentication business logic (no HTTP details here - see auth/router.py).

Key ideas, in plain words:

* LOGIN creates a row in refresh_sessions ("this browser is logged in") and gives
  the browser two things: a short-lived access JWT and a long-lived refresh token.
* REFRESH swaps the refresh token for a brand-new one every time (rotation). The
  old token's hash is remembered in previous_token_hash. If somebody later presents
  that old token again, it was probably stolen -> the whole session is revoked.
* LOGOUT / REVOKE set revoked_at. Because every protected request checks the
  session (auth/dependencies.py), the access token stops working immediately.
* BRUTE FORCE: every attempt is stored in login_attempts. 5 wrong passwords in a
  row lock the account for 15 minutes; too many failures from one IP -> HTTP 429.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from audit import client_ip, log_event, user_agent
from auth.dependencies import as_utc, session_is_active
from auth.schemas import LoginRequest, PasswordChange, ProfileUpdate, SignupRequest
from auth.security import (
    burn_time_for_unknown_user,
    hash_password,
    needs_rehash,
    password_problems,
    verify_password,
)
from auth.tokens import create_access_token, hash_token, new_refresh_token
from config import get_settings
from models import LoginAttempt, RefreshSession, User, UserRole

GENERIC_LOGIN_ERROR = "Invalid email or password"
# A second browser tab may refresh with the just-rotated token a moment after the
# first tab. Within this window an old token is rejected but NOT treated as theft.
REFRESH_REUSE_GRACE_SECONDS = 30


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _password_error(problems: list[str]) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Password must have " + ", ".join(problems) + ".",
    )


# --------------------------------------------------------------------- sessions

def create_session(session: Session, user: User, request: Request) -> tuple[RefreshSession, str]:
    raw = new_refresh_token()
    rs = RefreshSession(
        user_id=user.id,
        token_hash=hash_token(raw),  # only the hash is stored
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        expires_at=now_utc() + timedelta(days=get_settings().refresh_token_days),
    )
    session.add(rs)
    session.flush()  # assigns rs.id
    return rs, raw


def _access_for(user: User, rs: RefreshSession) -> tuple[str, int]:
    return create_access_token(user.id, user.role.value, rs.id)


def _revoke(rs: RefreshSession, reason: str) -> None:
    rs.revoked_at = now_utc()
    rs.revoked_reason = reason


# ----------------------------------------------------------------------- signup

def signup(session: Session, data: SignupRequest, request: Request):
    email = normalize_email(data.email)
    problems = password_problems(data.password, email)
    if problems:
        raise _password_error(problems)

    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email is already registered")

    user = User(
        email=email,
        full_name=data.full_name,
        password_hash=hash_password(data.password),
        role=UserRole.user,  # signup can NEVER create an admin
        password_changed_at=now_utc(),
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError:  # two signups with the same email at the same moment
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Email is already registered")

    rs, raw = create_session(session, user, request)
    log_event(session, "auth.signup", request=request, actor_id=user.id,
              target_type="user", target_id=user.id)
    session.commit()
    session.refresh(user)
    access, expires_in = _access_for(user, rs)
    return user, access, expires_in, raw


# ------------------------------------------------------------------------ login

def _record_attempt(session: Session, email: str, user: Optional[User], request: Request,
                    success: bool, reason: Optional[str] = None) -> None:
    session.add(LoginAttempt(
        email_attempted=email[:255],
        user_id=user.id if user else None,
        ip_address=client_ip(request),
        user_agent=user_agent(request),
        success=success,
        failure_reason=reason,
    ))


def _ip_is_rate_limited(session: Session, ip: Optional[str]) -> bool:
    if not ip:
        return False
    settings = get_settings()
    cutoff = now_utc() - timedelta(minutes=settings.ip_window_minutes)
    failures = session.exec(
        select(func.count()).select_from(LoginAttempt).where(
            LoginAttempt.ip_address == ip,
            LoginAttempt.success == False,  # noqa: E712 (SQL comparison)
            LoginAttempt.created_at >= cutoff,
        )
    ).one()
    return failures >= settings.ip_fail_limit


def login(session: Session, data: LoginRequest, request: Request):
    settings = get_settings()
    email = normalize_email(data.email)

    # 1. Too many failures from this IP address recently -> 429
    if _ip_is_rate_limited(session, client_ip(request)):
        _record_attempt(session, email, None, request, False, "ip_rate_limited")
        log_event(session, "auth.login_blocked", request=request,
                  details={"email": email, "reason": "ip_rate_limited"})
        session.commit()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts from your network. Try again later.",
            headers={"Retry-After": str(settings.ip_window_minutes * 60)},
        )

    user = session.exec(select(User).where(User.email == email)).first()

    # 2. Unknown email -> same generic message and similar timing as a wrong password
    if user is None:
        burn_time_for_unknown_user(data.password)
        _record_attempt(session, email, None, request, False, "unknown_email")
        log_event(session, "auth.login_failed", request=request,
                  details={"email": email, "reason": "unknown_email"})
        session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    now = now_utc()

    # 3. Account temporarily locked
    if user.locked_until and as_utc(user.locked_until) > now:
        minutes_left = max(1, int((as_utc(user.locked_until) - now).total_seconds() // 60) + 1)
        _record_attempt(session, email, user, request, False, "account_locked")
        log_event(session, "auth.login_failed", request=request, actor_id=user.id,
                  target_type="user", target_id=user.id, details={"reason": "account_locked"})
        session.commit()
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Account locked; try again in {minutes_left} minute(s).",
            headers={"Retry-After": str(minutes_left * 60)},
        )

    # 4. Wrong password
    if not verify_password(data.password, user.password_hash):
        user.failed_login_count += 1
        reason = "bad_password"
        if user.failed_login_count >= settings.lockout_threshold:
            user.locked_until = now + timedelta(minutes=settings.lockout_minutes)
            user.failed_login_count = 0
            reason = "bad_password_account_locked"
            log_event(session, "auth.account_locked", request=request, actor_id=user.id,
                      target_type="user", target_id=user.id,
                      details={"minutes": settings.lockout_minutes})
        _record_attempt(session, email, user, request, False, reason)
        log_event(session, "auth.login_failed", request=request, actor_id=user.id,
                  target_type="user", target_id=user.id, details={"reason": reason})
        session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=GENERIC_LOGIN_ERROR)

    # 5. Correct password but banned
    if user.is_banned:
        _record_attempt(session, email, user, request, False, "banned")
        log_event(session, "auth.login_failed", request=request, actor_id=user.id,
                  target_type="user", target_id=user.id, details={"reason": "banned"})
        session.commit()
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is banned")

    # 6. Success
    user.failed_login_count = 0
    user.locked_until = None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(data.password)
    _record_attempt(session, email, user, request, True)
    rs, raw = create_session(session, user, request)
    log_event(session, "auth.login", request=request, actor_id=user.id,
              target_type="session", target_id=rs.id)
    session.commit()
    session.refresh(user)
    access, expires_in = _access_for(user, rs)
    return user, access, expires_in, raw


# ---------------------------------------------------------------------- refresh

def refresh(session: Session, raw_token: Optional[str], request: Request):
    if not raw_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_hash = hash_token(raw_token)
    rs = session.exec(select(RefreshSession).where(RefreshSession.token_hash == token_hash)).first()

    if rs is None:
        # Was this token already rotated away? Then someone is replaying an old token.
        old = session.exec(
            select(RefreshSession).where(RefreshSession.previous_token_hash == token_hash)
        ).first()
        if old is not None and old.revoked_at is None:
            age = (now_utc() - as_utc(old.last_used_at)).total_seconds()
            if age > REFRESH_REUSE_GRACE_SECONDS:
                _revoke(old, "refresh_token_reuse")
                log_event(session, "auth.refresh_reuse_detected", request=request,
                          actor_id=old.user_id, target_type="session", target_id=old.id)
                session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if not session_is_active(rs):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Session has ended. Please log in again.")

    user = session.get(User, rs.user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    if user.is_banned:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Account is banned")

    # Rotation: issue a new refresh token, remember the old hash for reuse detection.
    new_raw = new_refresh_token()
    rs.previous_token_hash = rs.token_hash
    rs.token_hash = hash_token(new_raw)
    rs.last_used_at = now_utc()
    rs.ip_address = client_ip(request)
    rs.user_agent = user_agent(request)
    session.add(rs)
    session.commit()
    session.refresh(user)
    access, expires_in = _access_for(user, rs)
    return user, access, expires_in, new_raw


# ----------------------------------------------------------------------- logout

def logout(session: Session, raw_token: Optional[str], session_id: Optional[int], request: Request) -> None:
    targets: list[RefreshSession] = []
    if raw_token:
        rs = session.exec(
            select(RefreshSession).where(RefreshSession.token_hash == hash_token(raw_token))
        ).first()
        if rs:
            targets.append(rs)
    if session_id is not None:
        rs = session.get(RefreshSession, session_id)
        if rs and rs not in targets:
            targets.append(rs)

    for rs in targets:
        if rs.revoked_at is None:
            _revoke(rs, "logout")
            log_event(session, "auth.logout", request=request, actor_id=rs.user_id,
                      target_type="session", target_id=rs.id)
    session.commit()


# -------------------------------------------------------------- session management

def list_active_sessions(session: Session, user: User) -> list[RefreshSession]:
    rows = session.exec(
        select(RefreshSession)
        .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
        .order_by(RefreshSession.last_used_at.desc())
    ).all()
    return [rs for rs in rows if session_is_active(rs)]


def revoke_session(session: Session, user: User, session_id: int, request: Request) -> None:
    rs = session.get(RefreshSession, session_id)
    if rs is None or rs.user_id != user.id:  # other people's sessions look "not found"
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Session not found")
    if rs.revoked_at is None:
        _revoke(rs, "user_revoked")
        log_event(session, "session.revoke", request=request, actor_id=user.id,
                  target_type="session", target_id=rs.id)
        session.commit()


def revoke_other_sessions(session: Session, user: User, keep_session_id: Optional[int],
                          reason: str = "user_revoked_others") -> int:
    count = 0
    for rs in list_active_sessions(session, user):
        if rs.id != keep_session_id:
            _revoke(rs, reason)
            count += 1
    return count


# ------------------------------------------------------------- profile / password

def update_profile(session: Session, user: User, data: ProfileUpdate, request: Request) -> User:
    changed = []
    if data.full_name is not None and data.full_name.strip() != user.full_name:
        name = data.full_name.strip()
        if not name:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Full name is required")
        user.full_name = name
        changed.append("full_name")

    if data.email is not None and normalize_email(data.email) != user.email:
        if not data.current_password or not verify_password(data.current_password, user.password_hash):
            log_event(session, "user.profile_update_failed", request=request, actor_id=user.id,
                      target_type="user", target_id=user.id, details={"reason": "bad_current_password"})
            session.commit()
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                detail="Current password is required to change your email")
        new_email = normalize_email(data.email)
        if session.exec(select(User).where(User.email == new_email)).first():
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Email is already registered")
        user.email = new_email
        changed.append("email")

    if changed:
        user.updated_at = now_utc()
        session.add(user)
        log_event(session, "user.profile_update", request=request, actor_id=user.id,
                  target_type="user", target_id=user.id, details={"fields": changed})
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, detail="Email is already registered")
        session.refresh(user)
    return user


def change_password(session: Session, user: User, data: PasswordChange,
                    current_session_id: Optional[int], request: Request) -> int:
    if not verify_password(data.current_password, user.password_hash):
        # Recorded so admins can see repeated failures in the activity log.
        log_event(session, "user.password_change_failed", request=request, actor_id=user.id,
                  target_type="user", target_id=user.id, details={"reason": "bad_current_password"})
        session.commit()
        # 400, not 401: the user IS logged in; 401 would make the browser try to refresh.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    problems = password_problems(data.new_password, user.email)
    if problems:
        raise _password_error(problems)
    if verify_password(data.new_password, user.password_hash):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            detail="New password must be different from the current one")

    user.password_hash = hash_password(data.new_password)
    user.password_changed_at = now_utc()
    user.updated_at = now_utc()
    session.add(user)
    revoked = revoke_other_sessions(session, user, current_session_id, reason="password_changed")
    log_event(session, "user.password_change", request=request, actor_id=user.id,
              target_type="user", target_id=user.id, details={"other_sessions_revoked": revoked})
    session.commit()
    return revoked
