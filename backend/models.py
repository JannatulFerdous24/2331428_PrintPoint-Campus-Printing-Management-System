"""
Database models (tables) for PrintPoint.

Mid Project table:     print_requests
Final Project tables:  users, refresh_sessions, login_attempts, audit_logs,
                       groups, group_members, print_request_status_history

Every table here must have a matching Alembic migration in backend/migrations/.
tests/test_migrations.py fails if models and migrations ever disagree.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PrintType(str, Enum):
    black_and_white = "Black & White"
    color = "Color"


class RequestStatus(str, Enum):
    pending = "Pending"
    processing = "Processing"
    ready = "Ready"
    collected = "Collected"
    rejected = "Rejected"


class PaymentStatus(str, Enum):
    pending = "Pending"
    paid = "Paid"


class UserRole(str, Enum):
    """Stored role. UI labels: user -> "Student", admin -> "Print-Shop Staff (Admin)"."""
    user = "user"
    admin = "admin"


# Valid status transitions: key -> allowed next statuses (Final Project workflow):
#   Pending -> Processing -> Ready -> Collected      Pending -> Rejected
# Staff accept (Processing) or reject a request only while it is Pending;
# Collected and Rejected are final.
VALID_TRANSITIONS: dict[RequestStatus, list[RequestStatus]] = {
    RequestStatus.pending: [RequestStatus.processing, RequestStatus.rejected],
    RequestStatus.processing: [RequestStatus.ready],
    RequestStatus.ready: [RequestStatus.collected],
    RequestStatus.collected: [],
    RequestStatus.rejected: [],
}


# ---------------------------------------------------------------------------
# Users and authentication
# ---------------------------------------------------------------------------

class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(max_length=255, unique=True, index=True)  # stored lower-case
    full_name: str = Field(min_length=1, max_length=200)
    password_hash: str = Field(max_length=255)  # Argon2 hash, never the password
    role: UserRole = Field(default=UserRole.user, index=True)

    # Ban status (admins ban/unban; a banned user is rejected on the next request)
    is_banned: bool = Field(default=False, index=True)
    ban_reason: Optional[str] = Field(default=None, max_length=500)
    banned_at: Optional[datetime] = Field(default=None)
    banned_by_id: Optional[int] = Field(default=None, foreign_key="users.id", ondelete="SET NULL")

    # Brute-force protection
    failed_login_count: int = Field(default=0)
    locked_until: Optional[datetime] = Field(default=None)

    password_changed_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)


class RefreshSession(SQLModel, table=True):
    """One row = one login session (one device/browser).

    Only a SHA-256 hash of the refresh token is stored. On every refresh the
    token is rotated: the old hash moves to previous_token_hash. If that old
    token is ever presented again (token theft/reuse), the session is revoked.
    """
    __tablename__ = "refresh_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    token_hash: str = Field(max_length=64, unique=True, index=True)
    previous_token_hash: Optional[str] = Field(default=None, max_length=64, index=True)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now)
    last_used_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime
    revoked_at: Optional[datetime] = Field(default=None)
    revoked_reason: Optional[str] = Field(default=None, max_length=50)


class LoginAttempt(SQLModel, table=True):
    """Every login attempt (success or failure). Feeds lockout and the security view."""
    __tablename__ = "login_attempts"

    id: Optional[int] = Field(default=None, primary_key=True)
    email_attempted: str = Field(max_length=255, index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="users.id", ondelete="SET NULL", index=True)
    ip_address: Optional[str] = Field(default=None, max_length=45, index=True)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    success: bool = Field(default=False, index=True)
    failure_reason: Optional[str] = Field(default=None, max_length=50)
    created_at: datetime = Field(default_factory=utc_now, index=True)


class AuditLog(SQLModel, table=True):
    """Activity log: who did what, to what, from where and when.

    `action` is plain text (e.g. "auth.login", "user.ban") so new event types
    never need a database migration.
    """
    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    actor_id: Optional[int] = Field(default=None, foreign_key="users.id", ondelete="SET NULL", index=True)
    action: str = Field(max_length=50, index=True)
    target_type: Optional[str] = Field(default=None, max_length=50)
    target_id: Optional[str] = Field(default=None, max_length=50)
    details: Optional[dict[str, Any]] = Field(
        default=None, sa_type=JSON().with_variant(JSONB(), "postgresql")
    )
    ip_address: Optional[str] = Field(default=None, max_length=45, index=True)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=utc_now, index=True)


# ---------------------------------------------------------------------------
# Groups (class / club / student team) and fine-grained permissions
# ---------------------------------------------------------------------------

class Group(SQLModel, table=True):
    """Only the owner may rename/delete the group or manage its members."""
    __tablename__ = "groups"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    owner_id: int = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)


class GroupMember(SQLModel, table=True):
    """A user's membership in a group and what they may do inside it."""
    __tablename__ = "group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(foreign_key="groups.id", ondelete="CASCADE", index=True)
    user_id: int = Field(foreign_key="users.id", ondelete="CASCADE", index=True)
    can_create: bool = Field(default=False)  # create requests in the group
    can_edit: bool = Field(default=False)    # edit group requests (not status)
    can_assign: bool = Field(default=False)  # set assignee_id on group requests
    added_by_id: Optional[int] = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    joined_at: datetime = Field(default_factory=utc_now)


# ---------------------------------------------------------------------------
# Print requests
# ---------------------------------------------------------------------------

class PrintRequest(SQLModel, table=True):
    __tablename__ = "print_requests"

    # --- Mid Project fields (columns unchanged; 0002 only adds indexes on status/created_at) ---
    id: Optional[int] = Field(default=None, primary_key=True)
    student_name: str = Field(index=True, min_length=1, max_length=200)
    document_name: str = Field(min_length=1, max_length=500)
    copies: int = Field(ge=1, le=999)
    print_type: PrintType = Field(default=PrintType.black_and_white)
    status: RequestStatus = Field(default=RequestStatus.pending, index=True)
    notes: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)

    # --- Ownership and sharing (added in 0002; owner_id made required in 0003) ---
    owner_id: int = Field(foreign_key="users.id", ondelete="RESTRICT", index=True)
    group_id: Optional[int] = Field(default=None, foreign_key="groups.id", ondelete="SET NULL", index=True)
    assignee_id: Optional[int] = Field(default=None, foreign_key="users.id", ondelete="SET NULL", index=True)

    # --- Document metadata; the file itself lives in a PRIVATE Supabase Storage bucket ---
    storage_path: Optional[str] = Field(default=None, max_length=500)  # object key, never a public URL
    original_filename: Optional[str] = Field(default=None, max_length=255)
    content_type: Optional[str] = Field(default=None, max_length=100)
    file_size_bytes: Optional[int] = Field(default=None)
    uploaded_at: Optional[datetime] = Field(default=None)

    # --- Cost and payment (added in 0004). total_cost is in Taka and is ALWAYS
    # calculated by the server (pricing.py), never taken from the browser. ---
    pages: int = Field(default=1, ge=1, le=1000)
    total_cost: int = Field(default=0, ge=0)
    payment_status: PaymentStatus = Field(default=PaymentStatus.pending)
    paid_at: Optional[datetime] = Field(default=None)


class PrintRequestStatusHistory(SQLModel, table=True):
    """One row per status change, so we know when each status was set and by whom."""
    __tablename__ = "print_request_status_history"

    id: Optional[int] = Field(default=None, primary_key=True)
    print_request_id: int = Field(foreign_key="print_requests.id", ondelete="CASCADE", index=True)
    from_status: Optional[RequestStatus] = Field(default=None)  # None = request created
    to_status: RequestStatus
    changed_by_id: Optional[int] = Field(default=None, foreign_key="users.id", ondelete="SET NULL")
    note: Optional[str] = Field(default=None, max_length=500)
    changed_at: datetime = Field(default_factory=utc_now, index=True)
