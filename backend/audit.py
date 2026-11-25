"""
Audit (activity) log helper. One function so every event has the same shape:
who (actor), what (action), on what (target), from where (IP + browser), when.
The caller commits the database session.
"""

from typing import Any, Optional

from fastapi import Request
from sqlmodel import Session

from models import AuditLog


def client_ip(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    # Vercel puts the real client address first in X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:45]
    return request.client.host[:45] if request.client else None


def user_agent(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    ua = request.headers.get("user-agent")
    return ua[:500] if ua else None


def log_event(
    session: Session,
    action: str,
    *,
    request: Optional[Request] = None,
    actor_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[Any] = None,
    details: Optional[dict] = None,
) -> None:
    session.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            details=details,
            ip_address=client_ip(request),
            user_agent=user_agent(request),
        )
    )
