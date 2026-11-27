"""
Role-Based Access Control (RBAC) for PrintPoint - the ONE place where
"who may do what" is decided. Routers call these helpers; they never compare
roles themselves.

Roles (stored in users.role, exactly two - Final Project requirement):
    user   -> shown as "Student"
    admin  -> shown as "Print-Shop Staff (Admin)"  (staff ARE admins)

Three layers of rules:
  1. ROLE permissions      - what your role allows system-wide (ROLE_PERMISSIONS)
  2. OWNERSHIP / GROUPS    - what you may do with a specific request or group
  3. ADMIN SAFETY          - an admin cannot change their own role or ban an admin

HTTP answers:
  404 - you may not even SEE the item (so guessing IDs reveals nothing)
  403 - you can see it, but you may not do this action
The user is always re-loaded from the database (auth/dependencies.py), so a role
change or ban takes effect on the very next request, not when the JWT expires.
"""

from enum import Enum

from fastapi import Depends, HTTPException, status
from sqlmodel import Session, select

from auth.dependencies import get_current_user
from models import Group, GroupMember, PaymentStatus, PrintRequest, RequestStatus, User, UserRole

ROLE_LABELS = {UserRole.user: "Student", UserRole.admin: "Print-Shop Staff (Admin)"}


# --------------------------------------------------------------- 1. role level

class Permission(str, Enum):
    # own requests (everyone)
    REQUEST_CREATE = "request:create"
    REQUEST_READ_OWN = "request:read_own"
    REQUEST_UPDATE_OWN = "request:update_own"
    REQUEST_DELETE_OWN = "request:delete_own"
    GROUP_CREATE = "group:create"
    # staff / admin only
    REQUEST_READ_ALL = "request:read_all"
    REQUEST_UPDATE_STATUS = "request:update_status"
    PAYMENT_UPDATE = "request:update_payment"   # mark a request Paid / Pending
    MODERATE_CONTENT = "content:moderate"        # delete any request / group (audited)
    USER_READ = "user:read"
    USER_BAN = "user:ban"
    USER_CHANGE_ROLE = "user:change_role"
    USER_REVOKE_SESSIONS = "user:revoke_sessions"
    AUDIT_READ = "audit:read"
    DATA_EXPORT = "data:export"


_STUDENT = {
    Permission.REQUEST_CREATE, Permission.REQUEST_READ_OWN,
    Permission.REQUEST_UPDATE_OWN, Permission.REQUEST_DELETE_OWN, Permission.GROUP_CREATE,
}

ROLE_PERMISSIONS: dict[UserRole, frozenset[Permission]] = {
    UserRole.user: frozenset(_STUDENT),
    UserRole.admin: frozenset(Permission),  # every permission
}


def has_permission(user: User, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(user.role, frozenset())


def require_permission(*permissions: Permission):
    """FastAPI dependency factory: `user = Depends(require_permission(Permission.USER_BAN))`."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        missing = [p for p in permissions if not has_permission(user, p)]
        if missing:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                detail="You do not have permission to perform this action")
        return user

    return dependency


require_admin = require_permission(Permission.USER_READ)


def forbidden(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail=detail)


def not_found(what: str = "Not found") -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail=what)


# ------------------------------------------------------------- 2a. groups

class GroupPerm(str, Enum):
    VIEW = "view"        # any member (and admins, for oversight)
    CREATE = "create"    # owner or member with can_create
    EDIT = "edit"        # owner or member with can_edit
    ASSIGN = "assign"    # owner or member with can_assign
    MANAGE = "manage"    # OWNER ONLY: rename, delete group, manage members


def get_membership(session: Session, group_id: int, user_id: int) -> GroupMember | None:
    return session.exec(
        select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)
    ).first()


def group_flags(group: Group, membership: GroupMember | None, user: User) -> dict[str, bool]:
    """What this user may do inside this group (used by the API and shown to the UI)."""
    is_owner = group.owner_id == user.id
    return {
        "is_owner": is_owner,
        "is_member": is_owner or membership is not None,
        "can_create": is_owner or bool(membership and membership.can_create),
        "can_edit": is_owner or bool(membership and membership.can_edit),
        "can_assign": is_owner or bool(membership and membership.can_assign),
        "can_manage": is_owner,
    }


def load_group(session: Session, user: User, group_id: int, perm: GroupPerm) -> tuple[Group, dict]:
    """Return (group, flags) or raise 404 (not visible) / 403 (visible, not allowed)."""
    group = session.get(Group, group_id)
    if group is None:
        raise not_found("Group not found")
    flags = group_flags(group, get_membership(session, group_id, user.id), user)

    visible = flags["is_member"] or (perm == GroupPerm.VIEW and has_permission(user, Permission.REQUEST_READ_ALL))
    if not visible:
        raise not_found("Group not found")

    allowed = {
        GroupPerm.VIEW: True,
        GroupPerm.CREATE: flags["can_create"],
        GroupPerm.EDIT: flags["can_edit"],
        GroupPerm.ASSIGN: flags["can_assign"],
        GroupPerm.MANAGE: flags["can_manage"],
    }[perm]
    if not allowed:
        messages = {
            GroupPerm.CREATE: "You do not have permission to create requests in this group",
            GroupPerm.EDIT: "You do not have permission to edit requests in this group",
            GroupPerm.ASSIGN: "You do not have permission to assign requests in this group",
            GroupPerm.MANAGE: "Only the group owner can do this",
        }
        raise forbidden(messages[perm])
    return group, flags


def visible_group_ids(session: Session, user: User) -> list[int]:
    """Groups the user owns or belongs to."""
    member_of = session.exec(select(GroupMember.group_id).where(GroupMember.user_id == user.id)).all()
    owned = session.exec(select(Group.id).where(Group.owner_id == user.id)).all()
    return sorted(set(member_of) | set(owned))


# ----------------------------------------------------------- 2b. print requests

def request_permissions(session: Session, user: User, pr: PrintRequest) -> dict[str, bool]:
    """Everything this user may do with this request. Used for checks AND sent to the UI,
    so the frontend shows exactly the buttons the server will accept."""
    is_owner = pr.owner_id == user.id
    flags = None
    if pr.group_id is not None:
        group = session.get(Group, pr.group_id)
        if group is not None:
            flags = group_flags(group, get_membership(session, group.id, user.id), user)
    in_group = bool(flags and flags["is_member"])
    # Editable only while Pending and not yet paid (the paid amount must not change).
    editable = pr.status == RequestStatus.pending and pr.payment_status != PaymentStatus.paid

    return {
        "view": is_owner or in_group or has_permission(user, Permission.REQUEST_READ_ALL),
        "edit": editable and (is_owner or bool(flags and flags["can_edit"])),
        "delete": is_owner or bool(flags and flags["is_owner"]),
        "change_status": has_permission(user, Permission.REQUEST_UPDATE_STATUS),
        "assign": bool(flags and flags["can_assign"]),
        "update_payment": has_permission(user, Permission.PAYMENT_UPDATE),
    }


def get_visible_request(session: Session, user: User, request_id: int) -> tuple[PrintRequest, dict]:
    pr = session.get(PrintRequest, request_id)
    if pr is None:
        raise not_found(f"Print request {request_id} not found")
    perms = request_permissions(session, user, pr)
    if not perms["view"]:
        # Same answer as "does not exist": changing the ID in the URL reveals nothing.
        raise not_found(f"Print request {request_id} not found")
    return pr, perms


# ------------------------------------------------------------ 3. admin safety

def assert_can_change_role(actor: User, target: User) -> None:
    if actor.id == target.id:
        raise forbidden("Admins cannot change their own role")


def assert_can_ban(actor: User, target: User) -> None:
    if actor.id == target.id:
        raise forbidden("You cannot ban yourself")
    if target.role == UserRole.admin:
        raise forbidden("Admins cannot ban other admins")
