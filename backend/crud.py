from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException
from sqlmodel import Session, select
from models import PrintRequest, RequestStatus, VALID_TRANSITIONS
from schemas import PrintRequestCreate, PrintRequestUpdate


def create_print_request(session: Session, data: PrintRequestCreate) -> PrintRequest:
    request = PrintRequest(**data.model_dump())
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def get_print_request(session: Session, request_id: int) -> PrintRequest:
    request = session.get(PrintRequest, request_id)
    if not request:
        raise HTTPException(status_code=404, detail=f"Print request {request_id} not found")
    return request


def list_print_requests(
    session: Session,
    skip: int = 0,
    limit: int = 100,
    status: Optional[RequestStatus] = None,
) -> list[PrintRequest]:
    statement = select(PrintRequest)
    if status:
        statement = statement.where(PrintRequest.status == status)
    statement = statement.offset(skip).limit(limit).order_by(PrintRequest.created_at.desc())
    return list(session.exec(statement).all())


def update_print_request(
    session: Session, request_id: int, data: PrintRequestUpdate
) -> PrintRequest:
    request = get_print_request(session, request_id)

    update_data = data.model_dump(exclude_unset=True)

    # Validate status transition if status is being changed
    if "status" in update_data and update_data["status"] != request.status:
        new_status = update_data["status"]
        allowed = VALID_TRANSITIONS.get(request.status, [])
        if new_status not in allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Cannot transition from '{request.status.value}' to '{new_status.value}'. "
                       f"Allowed transitions: {[s.value for s in allowed] or 'none'}",
            )

    for key, value in update_data.items():
        setattr(request, key, value)

    request.updated_at = datetime.now(timezone.utc)
    session.add(request)
    session.commit()
    session.refresh(request)
    return request


def delete_print_request(session: Session, request_id: int) -> None:
    request = get_print_request(session, request_id)
    session.delete(request)
    session.commit()
