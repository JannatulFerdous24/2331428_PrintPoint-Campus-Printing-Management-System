"""
/api/admin - privileged actions for the `admin` role (print-shop staff and
system administrators). Every endpoint requires an admin permission (403 for
students) and every change is written to the audit log.

  dashboard   GET  /stats                       real counts from the database
  users       GET  /users (q, role, banned, paging; X-Total-Count)
              GET  /users/{id}                  detail: requests, groups, sessions, activity
              POST /users/{id}/ban | unban | revoke-sessions,  PATCH /users/{id}/role
              POST /users/bulk-ban | bulk-unban
  moderation  GET  /groups (q, paging)          requests use GET /api/print-requests (admin = all)
              DELETE /print-requests/{id}, /groups/{id}
              POST /print-requests/bulk-delete, /groups/bulk-delete
  activity    GET  /audit-logs (filters, paging)
  security    GET  /security/failed-logins       by IP address and by account
  exports     GET  /export/users.csv | print-requests.csv | audit-logs.csv  (same filters)

Safety rules (rbac.py): an admin cannot change their own role and cannot ban
another admin (or themselves) - also enforced for bulk actions.
"""

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlmodel import Session, select

import crud
from audit import log_event
from auth.dependencies import as_utc
from auth.service import list_active_sessions, revoke_other_sessions
from database import get_session
from models import (AuditLog, Group, GroupMember, LoginAttempt, PrintRequest, RequestStatus,
                    User, UserRole)
from rbac import Permission, assert_can_ban, assert_can_change_role, require_permission
from routers.groups import delete_group_and_detach
from routers.print_requests import list_filters
from storage import Storage, delete_quietly, get_optional_storage

router = APIRouter(prefix="/api/admin", tags=["admin"])
MAX_BULK = 200
MAX_EXPORT_ROWS = 10_000


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AdminUserRead(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_banned: bool
    ban_reason: Optional[str]
    banned_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class BanRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class RoleChange(BaseModel):
    role: UserRole


class BulkUsers(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=MAX_BULK)
    reason: Optional[str] = Field(default=None, max_length=500)


class BulkIds(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=MAX_BULK)


class BulkResult(BaseModel):
    done: list[int]
    skipped: list[dict[str, Any]]  # [{"id": 3, "reason": "..."}]


class AuditLogRead(BaseModel):
    id: int
    created_at: datetime
    action: str
    actor_id: Optional[int]
    actor_email: Optional[str] = None
    target_type: Optional[str]
    target_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    details: Optional[dict[str, Any]]

    model_config = {"from_attributes": True}


def _target(session: Session, user_id: int) -> User:
    target = session.get(User, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="User not found")
    return target


def _count(session: Session, model, *conds) -> int:
    return session.exec(select(func.count()).select_from(model).where(*conds)).one()


# ------------------------------------------------------------------ dashboard

@router.get("/stats")
def stats(session: Session = Depends(get_session),
          admin: User = Depends(require_permission(Permission.USER_READ))):
    week = _now() - timedelta(days=7)
    day = _now() - timedelta(hours=24)
    by_status = dict(session.exec(select(PrintRequest.status, func.count()).group_by(PrintRequest.status)).all())
    return {
        "total_users": _count(session, User),
        "banned_users": _count(session, User, User.is_banned == True),  # noqa: E712
        "admins": _count(session, User, User.role == UserRole.admin),
        "total_requests": _count(session, PrintRequest),
        "requests_by_status": {s.value: by_status.get(s, 0) for s in RequestStatus},
        "total_groups": _count(session, Group),
        "new_users_7d": _count(session, User, User.created_at >= week),
        "new_requests_7d": _count(session, PrintRequest, PrintRequest.created_at >= week),
        "failed_logins_24h": _count(session, LoginAttempt, LoginAttempt.success == False,  # noqa: E712
                                    LoginAttempt.created_at >= day),
    }


# ------------------------------------------------------------------ users

def user_filters(q: Optional[str] = Query(default=None, max_length=100),
                 role: Optional[UserRole] = None, banned: Optional[bool] = None) -> list:
    conds = []
    if q and q.strip():
        like = f"%{q.strip()}%"
        conds.append(or_(User.email.ilike(like), User.full_name.ilike(like)))
    if role is not None:
        conds.append(User.role == role)
    if banned is not None:
        conds.append(User.is_banned == banned)
    return conds


@router.get("/users", response_model=list[AdminUserRead])
def list_users(response: Response, conds: list = Depends(user_filters),
               skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200),
               session: Session = Depends(get_session),
               admin: User = Depends(require_permission(Permission.USER_READ))):
    response.headers["X-Total-Count"] = str(_count(session, User, *conds))
    return session.exec(select(User).where(*conds).order_by(User.created_at.desc(), User.id.desc())
                        .offset(skip).limit(limit)).all()


@router.get("/users/{user_id}")
def user_detail(user_id: int, session: Session = Depends(get_session),
                admin: User = Depends(require_permission(Permission.USER_READ))):
    target = _target(session, user_id)
    requests, total_requests = crud.query_print_requests(
        session, crud.request_filters(owner_id=target.id), limit=50)
    owned = session.exec(select(Group).where(Group.owner_id == target.id)).all()
    member_rows = session.exec(select(Group, GroupMember).join(GroupMember, GroupMember.group_id == Group.id)
                               .where(GroupMember.user_id == target.id)).all()
    groups = {g.id: {"id": g.id, "name": g.name, "role": "owner"} for g in owned}
    for g, m in member_rows:
        groups.setdefault(g.id, {"id": g.id, "name": g.name, "role": "member",
                                 "can_create": m.can_create, "can_edit": m.can_edit, "can_assign": m.can_assign})
    activity = session.exec(
        select(AuditLog).where(or_(AuditLog.actor_id == target.id,
                                   (AuditLog.target_type == "user") & (AuditLog.target_id == str(target.id))))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(30)).all()
    return {
        "user": AdminUserRead.model_validate(target).model_dump(),
        "locked_until": target.locked_until,
        "failed_login_count": target.failed_login_count,
        "requests_total": total_requests,
        "requests": [{"id": r.id, "document_name": r.document_name, "status": r.status.value,
                      "copies": r.copies, "print_type": r.print_type.value, "created_at": r.created_at}
                     for r in requests],
        "groups": list(groups.values()),
        "sessions": [{"id": s.id, "ip_address": s.ip_address, "user_agent": s.user_agent,
                      "created_at": s.created_at, "last_used_at": s.last_used_at, "expires_at": s.expires_at}
                     for s in list_active_sessions(session, target)],
        "activity": [AuditLogRead.model_validate(a).model_dump() for a in activity],
    }


def _ban(session: Session, admin: User, target: User, reason: str, request: Request) -> None:
    assert_can_ban(admin, target)  # not yourself, not another admin
    target.is_banned = True
    target.ban_reason = reason.strip()
    target.banned_at = _now()
    target.banned_by_id = admin.id
    session.add(target)
    revoked = revoke_other_sessions(session, target, keep_session_id=None, reason="banned")
    log_event(session, "user.ban", request=request, actor_id=admin.id, target_type="user",
              target_id=target.id, details={"reason": target.ban_reason, "sessions_revoked": revoked})


def _unban(session: Session, admin: User, target: User, request: Request) -> None:
    target.is_banned = False
    target.ban_reason = None
    target.banned_at = None
    target.banned_by_id = None
    session.add(target)
    log_event(session, "user.unban", request=request, actor_id=admin.id, target_type="user",
              target_id=target.id)


@router.post("/users/{user_id}/ban", response_model=AdminUserRead)
def ban_user(user_id: int, data: BanRequest, request: Request, session: Session = Depends(get_session),
             admin: User = Depends(require_permission(Permission.USER_BAN))):
    target = _target(session, user_id)
    _ban(session, admin, target, data.reason, request)
    session.commit()
    session.refresh(target)
    return target


@router.post("/users/{user_id}/unban", response_model=AdminUserRead)
def unban_user(user_id: int, request: Request, session: Session = Depends(get_session),
               admin: User = Depends(require_permission(Permission.USER_BAN))):
    target = _target(session, user_id)
    _unban(session, admin, target, request)
    session.commit()
    session.refresh(target)
    return target


@router.post("/users/bulk-ban", response_model=BulkResult)
def bulk_ban(data: BulkUsers, request: Request, session: Session = Depends(get_session),
             admin: User = Depends(require_permission(Permission.USER_BAN))):
    reason = (data.reason or "").strip()
    if len(reason) < 3:
        raise HTTPException(422, detail="A ban reason of at least 3 characters is required")
    done, skipped = [], []
    for uid in dict.fromkeys(data.user_ids):  # de-duplicated, order kept
        target = session.get(User, uid)
        if target is None:
            skipped.append({"id": uid, "reason": "User not found"})
        elif target.is_banned:
            skipped.append({"id": uid, "reason": "Already banned"})
        else:
            try:
                _ban(session, admin, target, reason, request)
                done.append(uid)
            except HTTPException as exc:  # safety rule: self / another admin
                skipped.append({"id": uid, "reason": exc.detail})
    session.commit()
    return BulkResult(done=done, skipped=skipped)


@router.post("/users/bulk-unban", response_model=BulkResult)
def bulk_unban(data: BulkUsers, request: Request, session: Session = Depends(get_session),
               admin: User = Depends(require_permission(Permission.USER_BAN))):
    done, skipped = [], []
    for uid in dict.fromkeys(data.user_ids):
        target = session.get(User, uid)
        if target is None:
            skipped.append({"id": uid, "reason": "User not found"})
        elif not target.is_banned:
            skipped.append({"id": uid, "reason": "Not banned"})
        else:
            _unban(session, admin, target, request)
            done.append(uid)
    session.commit()
    return BulkResult(done=done, skipped=skipped)


@router.post("/users/{user_id}/revoke-sessions")
def revoke_user_sessions(user_id: int, request: Request, session: Session = Depends(get_session),
                         admin: User = Depends(require_permission(Permission.USER_REVOKE_SESSIONS))):
    target = _target(session, user_id)
    if target.id == admin.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            detail="Use the Sessions page to manage your own sessions")
    revoked = revoke_other_sessions(session, target, keep_session_id=None, reason="admin_revoked")
    log_event(session, "user.sessions_revoke", request=request, actor_id=admin.id, target_type="user",
              target_id=target.id, details={"sessions_revoked": revoked})
    session.commit()
    return {"revoked": revoked}


@router.patch("/users/{user_id}/role", response_model=AdminUserRead)
def change_role(user_id: int, data: RoleChange, request: Request, session: Session = Depends(get_session),
                admin: User = Depends(require_permission(Permission.USER_CHANGE_ROLE))):
    target = _target(session, user_id)
    assert_can_change_role(admin, target)  # never your own role
    old = target.role
    if old != data.role:
        target.role = data.role
        target.updated_at = _now()
        session.add(target)
        log_event(session, "user.role_change", request=request, actor_id=admin.id, target_type="user",
                  target_id=target.id, details={"from": old.value, "to": data.role.value})
        session.commit()
        session.refresh(target)
    return target


# ------------------------------------------------------------- moderation

@router.get("/groups")
def list_all_groups(response: Response, q: Optional[str] = Query(default=None, max_length=100),
                    skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200),
                    session: Session = Depends(get_session),
                    admin: User = Depends(require_permission(Permission.MODERATE_CONTENT))):
    conds = []
    if q and q.strip():
        like = f"%{q.strip()}%"
        conds.append(or_(Group.name.ilike(like), Group.description.ilike(like),
                         Group.owner_id.in_(select(User.id).where(User.email.ilike(like)))))
    response.headers["X-Total-Count"] = str(_count(session, Group, *conds))
    rows = session.exec(select(Group, User.email).join(User, User.id == Group.owner_id).where(*conds)
                        .order_by(Group.created_at.desc(), Group.id.desc()).offset(skip).limit(limit)).all()
    return [{"id": g.id, "name": g.name, "description": g.description, "owner_id": g.owner_id,
             "owner_email": email, "created_at": g.created_at,
             "member_count": _count(session, GroupMember, GroupMember.group_id == g.id),
             "request_count": _count(session, PrintRequest, PrintRequest.group_id == g.id)}
            for g, email in rows]


def _moderate_request(session, pr, admin, request) -> Optional[str]:
    return crud.delete_print_request(session, pr, actor=admin, request=request, moderation=True)


def _moderate_group(session, group, admin, request) -> None:
    name, owner, gid = group.name, group.owner_id, group.id
    kept = delete_group_and_detach(session, group)
    log_event(session, "moderation.group_delete", request=request, actor_id=admin.id, target_type="group",
              target_id=gid, details={"name": name, "owner_id": owner, "requests_kept": kept})
    session.commit()


@router.delete("/print-requests/{request_id}", status_code=204)
def moderate_delete_request(request_id: int, request: Request, session: Session = Depends(get_session),
                            admin: User = Depends(require_permission(Permission.MODERATE_CONTENT)),
                            storage: Optional[Storage] = Depends(get_optional_storage)):
    pr = session.get(PrintRequest, request_id)
    if pr is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Print request {request_id} not found")
    delete_quietly(storage, _moderate_request(session, pr, admin, request))


@router.post("/print-requests/bulk-delete", response_model=BulkResult)
def bulk_delete_requests(data: BulkIds, request: Request, session: Session = Depends(get_session),
                         admin: User = Depends(require_permission(Permission.MODERATE_CONTENT)),
                         storage: Optional[Storage] = Depends(get_optional_storage)):
    done, skipped, files = [], [], []
    for rid in dict.fromkeys(data.ids):
        pr = session.get(PrintRequest, rid)
        if pr is None:
            skipped.append({"id": rid, "reason": "Not found"})
            continue
        files.append(_moderate_request(session, pr, admin, request))
        done.append(rid)
    for path in files:
        delete_quietly(storage, path)
    return BulkResult(done=done, skipped=skipped)


@router.delete("/groups/{group_id}", status_code=204)
def moderate_delete_group(group_id: int, request: Request, session: Session = Depends(get_session),
                          admin: User = Depends(require_permission(Permission.MODERATE_CONTENT))):
    group = session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Group not found")
    _moderate_group(session, group, admin, request)


@router.post("/groups/bulk-delete", response_model=BulkResult)
def bulk_delete_groups(data: BulkIds, request: Request, session: Session = Depends(get_session),
                       admin: User = Depends(require_permission(Permission.MODERATE_CONTENT))):
    done, skipped = [], []
    for gid in dict.fromkeys(data.ids):
        group = session.get(Group, gid)
        if group is None:
            skipped.append({"id": gid, "reason": "Not found"})
            continue
        _moderate_group(session, group, admin, request)
        done.append(gid)
    return BulkResult(done=done, skipped=skipped)


# ------------------------------------------------------------- activity log

def audit_filters(action: Optional[str] = Query(default=None, max_length=50,
                                                description="Exact action, or a prefix ending in '.' (e.g. auth.)"),
                  actor: Optional[str] = Query(default=None, max_length=100, description="Actor email contains"),
                  ip: Optional[str] = Query(default=None, max_length=45),
                  q: Optional[str] = Query(default=None, max_length=100),
                  date_from: Optional[datetime] = None, date_to: Optional[datetime] = None) -> list:
    conds = []
    if action:
        conds.append(AuditLog.action.startswith(action) if action.endswith(".") else AuditLog.action == action)
    if actor and actor.strip():
        conds.append(AuditLog.actor_id.in_(select(User.id).where(User.email.ilike(f"%{actor.strip()}%"))))
    if ip:
        conds.append(AuditLog.ip_address == ip.strip())
    if q and q.strip():
        like = f"%{q.strip()}%"
        conds.append(or_(AuditLog.action.ilike(like), AuditLog.target_id.ilike(like),
                         AuditLog.ip_address.ilike(like), AuditLog.user_agent.ilike(like)))
    if date_from:  # dates without a timezone are treated as UTC
        conds.append(AuditLog.created_at >= as_utc(date_from))
    if date_to:
        conds.append(AuditLog.created_at <= as_utc(date_to))
    return conds


def _audit_rows(session, conds, skip, limit) -> list[AuditLogRead]:
    rows = session.exec(select(AuditLog, User.email).join(User, User.id == AuditLog.actor_id, isouter=True)
                        .where(*conds).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                        .offset(skip).limit(limit)).all()
    out = []
    for log, email in rows:
        item = AuditLogRead.model_validate(log)
        item.actor_email = email
        out.append(item)
    return out


@router.get("/audit-logs", response_model=list[AuditLogRead])
def list_audit_logs(response: Response, conds: list = Depends(audit_filters),
                    skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=200),
                    session: Session = Depends(get_session),
                    admin: User = Depends(require_permission(Permission.AUDIT_READ))):
    response.headers["X-Total-Count"] = str(_count(session, AuditLog, *conds))
    return _audit_rows(session, conds, skip, limit)


# ------------------------------------------------------------- security view

@router.get("/security/failed-logins")
def failed_logins(hours: int = Query(default=24, ge=1, le=24 * 30),
                  session: Session = Depends(get_session),
                  admin: User = Depends(require_permission(Permission.AUDIT_READ))):
    since = _now() - timedelta(hours=hours)
    failed = [LoginAttempt.success == False, LoginAttempt.created_at >= since]  # noqa: E712
    by_ip = session.exec(
        select(LoginAttempt.ip_address, func.count(), func.count(func.distinct(LoginAttempt.email_attempted)),
               func.max(LoginAttempt.created_at))
        .where(*failed).group_by(LoginAttempt.ip_address).order_by(func.count().desc()).limit(100)).all()
    by_account = session.exec(
        select(LoginAttempt.email_attempted, func.count(), func.max(LoginAttempt.created_at),
               func.max(LoginAttempt.user_id))
        .where(*failed).group_by(LoginAttempt.email_attempted).order_by(func.count().desc()).limit(100)).all()
    locked = {u.id: u.locked_until for u in session.exec(select(User).where(User.locked_until.is_not(None))).all()}
    return {
        "hours": hours,
        "total_failed": _count(session, LoginAttempt, *failed),
        "by_ip": [{"ip_address": ip, "failures": n, "accounts_tried": accounts, "last_attempt": last}
                  for ip, n, accounts, last in by_ip],
        "by_account": [{"email": email, "user_id": uid, "failures": n, "last_attempt": last,
                        "known_account": uid is not None, "locked_until": locked.get(uid)}
                       for email, n, last, uid in by_account],
    }


# ------------------------------------------------------------- CSV exports

def _cell(value) -> str:
    """Plain text for CSV; values starting with = + - @ get a ' prefix so spreadsheet
    programs never run them as formulas (CSV injection)."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    text = getattr(value, "value", value)
    text = str(text)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _csv(session, request, admin, kind: str, header: list[str], rows: list[list], filters: dict) -> Response:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    log_event(session, "data.export", request=request, actor_id=admin.id, target_type=kind,
              details={"rows": len(rows), "filters": {k: _cell(v) for k, v in filters.items() if v not in (None, "")}})
    session.commit()
    name = f"printpoint-{kind}-{_now():%Y%m%d-%H%M%S}.csv"
    return Response(content="﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export/users.csv")
def export_users(request: Request, q: Optional[str] = Query(default=None, max_length=100),
                 role: Optional[UserRole] = None, banned: Optional[bool] = None,
                 session: Session = Depends(get_session),
                 admin: User = Depends(require_permission(Permission.DATA_EXPORT))):
    conds = user_filters(q, role, banned)
    users = session.exec(select(User).where(*conds).order_by(User.created_at.desc()).limit(MAX_EXPORT_ROWS)).all()
    rows = [[u.id, u.email, u.full_name, u.role, u.is_banned, u.ban_reason, u.banned_at, u.created_at]
            for u in users]
    return _csv(session, request, admin, "users",
                ["id", "email", "full_name", "role", "is_banned", "ban_reason", "banned_at", "created_at"],
                rows, {"q": q, "role": role, "banned": banned})


@router.get("/export/print-requests.csv")
def export_requests(request: Request, filters: dict = Depends(list_filters),
                    session: Session = Depends(get_session),
                    admin: User = Depends(require_permission(Permission.DATA_EXPORT))):
    reqs, _ = crud.query_print_requests(session, crud.request_filters(**filters), limit=MAX_EXPORT_ROWS)
    emails = dict(session.exec(select(User.id, User.email)).all())
    rows = [[r.id, r.student_name, emails.get(r.owner_id), r.document_name, r.original_filename, r.pages,
             r.copies, r.print_type, r.total_cost, r.payment_status, r.paid_at, r.status, r.group_id, r.created_at, r.updated_at] for r in reqs]
    return _csv(session, request, admin, "print-requests",
                ["id", "student_name", "owner_email", "document_name", "uploaded_file", "pages", "copies", "print_type",
                 "total_cost_bdt", "payment_status", "paid_at", "status", "group_id", "created_at", "updated_at"], rows, filters)


@router.get("/export/audit-logs.csv")
def export_audit(request: Request, conds: list = Depends(audit_filters),
                 action: Optional[str] = None, actor: Optional[str] = None, ip: Optional[str] = None,
                 q: Optional[str] = None, date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
                 session: Session = Depends(get_session),
                 admin: User = Depends(require_permission(Permission.DATA_EXPORT))):
    logs = _audit_rows(session, conds, 0, MAX_EXPORT_ROWS)
    rows = [[a.id, a.created_at, a.action, a.actor_email, a.target_type, a.target_id, a.ip_address,
             a.user_agent, a.details] for a in logs]
    return _csv(session, request, admin, "audit-logs",
                ["id", "time", "action", "actor_email", "target_type", "target_id", "ip_address",
                 "user_agent", "details"], rows,
                {"action": action, "actor": actor, "ip": ip, "q": q, "date_from": date_from, "date_to": date_to})
