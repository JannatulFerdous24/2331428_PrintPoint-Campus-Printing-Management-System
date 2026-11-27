"""
Database operations for print requests. Authorization decisions are made in
rbac.py and the routers; this module only reads/writes data consistently
(including status history and audit entries).
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Request
from sqlalchemy import func, or_
from sqlmodel import Session, select

from audit import log_event
from auth.dependencies import as_utc
from models import (
    VALID_TRANSITIONS,
    PaymentStatus,
    PrintRequest,
    PrintRequestStatusHistory,
    PrintType,
    RequestStatus,
    User,
)
from pricing import calculate_cost
from schemas import PrintRequestCreate, PrintRequestUpdate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_print_request(
    session: Session, data: PrintRequestCreate, owner_id: int, request: Optional[Request] = None
) -> PrintRequest:
    pr = PrintRequest(**data.model_dump(), owner_id=owner_id)
    pr.total_cost = calculate_cost(pr.pages, pr.copies, pr.print_type)  # server-side price
    session.add(pr)
    session.flush()
    # First history entry: "created as Pending" (from_status = None).
    session.add(PrintRequestStatusHistory(
        print_request_id=pr.id, from_status=None, to_status=pr.status, changed_by_id=owner_id,
    ))
    log_event(session, "request.create", request=request, actor_id=owner_id,
              target_type="print_request", target_id=pr.id,
              details={"group_id": pr.group_id} if pr.group_id else None)
    session.commit()
    session.refresh(pr)
    return pr


def get_print_request(session: Session, request_id: int) -> PrintRequest:
    pr = session.get(PrintRequest, request_id)
    if not pr:
        raise HTTPException(status_code=404, detail=f"Print request {request_id} not found")
    return pr


def request_filters(
    *,
    visible_to: Optional[tuple[int, list[int]]] = None,
    status: Optional[RequestStatus] = None,
    group_id: Optional[int] = None,
    q: Optional[str] = None,
    print_type: Optional[PrintType] = None,
    created_from: Optional[datetime] = None,
    created_to: Optional[datetime] = None,
    has_document: Optional[bool] = None,
    owner_id: Optional[int] = None,
    payment_status: Optional[PaymentStatus] = None,
) -> list:
    """WHERE conditions shared by the list, the staff queue and the CSV export.
    visible_to=(user_id, group_ids) limits results to the user's own requests and
    requests of their groups. None = everything (admins)."""
    conds = []
    if visible_to is not None:
        user_id, group_ids = visible_to
        own = [PrintRequest.owner_id == user_id]
        if group_ids:
            own.append(PrintRequest.group_id.in_(group_ids))
        conds.append(or_(*own))
    if status:
        conds.append(PrintRequest.status == status)
    if group_id is not None:
        conds.append(PrintRequest.group_id == group_id)
    if owner_id is not None:
        conds.append(PrintRequest.owner_id == owner_id)
    if print_type:
        conds.append(PrintRequest.print_type == print_type)
    if payment_status:
        conds.append(PrintRequest.payment_status == payment_status)
    if created_from:  # dates without a timezone are treated as UTC
        conds.append(PrintRequest.created_at >= as_utc(created_from))
    if created_to:
        conds.append(PrintRequest.created_at <= as_utc(created_to))
    if has_document is not None:
        conds.append(PrintRequest.storage_path.is_not(None) if has_document else PrintRequest.storage_path.is_(None))
    if q and q.strip():
        term = q.strip()
        like = f"%{term}%"
        owner_match = select(User.id).where(User.email.ilike(like))
        text_match = [PrintRequest.student_name.ilike(like), PrintRequest.document_name.ilike(like),
                      PrintRequest.original_filename.ilike(like), PrintRequest.owner_id.in_(owner_match)]
        if term.lstrip("#").isdigit():
            text_match.append(PrintRequest.id == int(term.lstrip("#")))
        conds.append(or_(*text_match))
    return conds


def query_print_requests(session: Session, conds: list, *, skip: int = 0, limit: int = 100,
                         sort: str = "newest") -> tuple[list[PrintRequest], int]:
    total = session.exec(select(func.count()).select_from(PrintRequest).where(*conds)).one()
    order = PrintRequest.created_at.asc() if sort == "oldest" else PrintRequest.created_at.desc()
    rows = session.exec(select(PrintRequest).where(*conds)
                        .order_by(order, PrintRequest.id).offset(skip).limit(limit)).all()
    return list(rows), total


def list_print_requests(
    session: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[RequestStatus] = None,
    *,
    visible_to: Optional[tuple[int, list[int]]] = None,
    group_id: Optional[int] = None,
) -> list[PrintRequest]:
    """Mid Project signature, kept for compatibility."""
    conds = request_filters(visible_to=visible_to, status=status, group_id=group_id)
    return query_print_requests(session, conds, skip=skip, limit=limit)[0]


def validate_transition(current: RequestStatus, new: RequestStatus) -> None:
    allowed = VALID_TRANSITIONS.get(current, [])
    if new not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot transition from '{current.value}' to '{new.value}'. "
                   f"Allowed transitions: {[s.value for s in allowed] or 'none'}",
        )


MIN_REASON_LENGTH = 5


def rejection_reason(session: Session, pr: PrintRequest) -> Optional[str]:
    """The reason staff gave when rejecting this request (stored in the status history)."""
    if pr.status != RequestStatus.rejected:
        return None
    row = session.exec(
        select(PrintRequestStatusHistory)
        .where(PrintRequestStatusHistory.print_request_id == pr.id,
               PrintRequestStatusHistory.to_status == RequestStatus.rejected)
        .order_by(PrintRequestStatusHistory.id.desc())
    ).first()
    return row.note if row else None


def update_print_request(
    session: Session, pr: PrintRequest, data: PrintRequestUpdate, actor: User,
    request: Optional[Request] = None,
) -> PrintRequest:
    update_data = data.model_dump(exclude_unset=True)
    new_status = update_data.pop("status", None)
    reason = (update_data.pop("reason", None) or "").strip() or None
    status_change = new_status is not None and new_status != pr.status

    if reason and not status_change:
        raise HTTPException(status_code=422,
                            detail="A reason can only be given together with a status change")

    if status_change:
        validate_transition(pr.status, new_status)
        if new_status == RequestStatus.rejected and (reason is None or len(reason) < MIN_REASON_LENGTH):
            raise HTTPException(
                status_code=422,
                detail=f"A reason of at least {MIN_REASON_LENGTH} characters is required to reject a request",
            )
        old_status = pr.status
        pr.status = new_status
        # Who changed the status, when, and (optionally / for rejections) why.
        session.add(PrintRequestStatusHistory(
            print_request_id=pr.id, from_status=old_status, to_status=new_status,
            changed_by_id=actor.id, note=reason,
        ))
        details = {"from": old_status.value, "to": new_status.value}
        if reason:
            details["reason"] = reason
        log_event(session, "request.status_change", request=request, actor_id=actor.id,
                  target_type="print_request", target_id=pr.id, details=details)

    for key, value in update_data.items():
        setattr(pr, key, value)
    if {"pages", "copies", "print_type"} & update_data.keys():
        pr.total_cost = calculate_cost(pr.pages, pr.copies, pr.print_type)
    if update_data:
        log_event(session, "request.update", request=request, actor_id=actor.id,
                  target_type="print_request", target_id=pr.id,
                  details={"fields": sorted(update_data)})

    pr.updated_at = _now()
    session.add(pr)
    session.commit()
    session.refresh(pr)
    return pr


def update_payment_status(
    session: Session, pr: PrintRequest, new_status: PaymentStatus, actor: User,
    request: Optional[Request] = None,
) -> PrintRequest:
    """Staff mark a request Paid (or back to Pending to correct a mistake). No real
    payment gateway - this only records that the student paid at the counter."""
    if new_status == PaymentStatus.paid and pr.status == RequestStatus.rejected:
        raise HTTPException(status_code=409, detail="A rejected request cannot be marked as paid")
    if new_status == pr.payment_status:
        return pr
    old = pr.payment_status
    pr.payment_status = new_status
    pr.paid_at = _now() if new_status == PaymentStatus.paid else None
    pr.updated_at = _now()
    session.add(pr)
    log_event(session, "request.payment", request=request, actor_id=actor.id,
              target_type="print_request", target_id=pr.id,
              details={"from": old.value, "to": new_status.value, "amount": pr.total_cost})
    session.commit()
    session.refresh(pr)
    return pr


def delete_print_request(
    session: Session, pr: PrintRequest, actor: User, request: Optional[Request] = None,
    *, moderation: bool = False,
) -> Optional[str]:
    """Deletes the request and its history. Returns the stored document's key (if any)
    so the caller can remove the file from storage AFTER the database commit."""
    storage_path = pr.storage_path
    for h in session.exec(select(PrintRequestStatusHistory).where(
            PrintRequestStatusHistory.print_request_id == pr.id)).all():
        session.delete(h)
    session.flush()  # delete history rows BEFORE the request (explicit order, no cascade surprise)
    log_event(session, "moderation.request_delete" if moderation else "request.delete",
              request=request, actor_id=actor.id, target_type="print_request", target_id=pr.id,
              details={"owner_id": pr.owner_id, "group_id": pr.group_id,
                       "document_name": pr.document_name})
    session.delete(pr)
    session.commit()
    return storage_path
