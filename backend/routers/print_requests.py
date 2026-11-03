from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from database import get_session
from models import RequestStatus
from schemas import PrintRequestCreate, PrintRequestRead, PrintRequestUpdate
import crud

router = APIRouter(prefix="/api/print-requests", tags=["print-requests"])


@router.post("", response_model=PrintRequestRead, status_code=201)
def create_print_request(
    data: PrintRequestCreate, session: Session = Depends(get_session)
):
    return crud.create_print_request(session, data)


@router.get("", response_model=list[PrintRequestRead])
def list_print_requests(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    status: Optional[RequestStatus] = Query(default=None),
    session: Session = Depends(get_session),
):
    return crud.list_print_requests(session, skip=skip, limit=limit, status=status)


@router.get("/{request_id}", response_model=PrintRequestRead)
def get_print_request(request_id: int, session: Session = Depends(get_session)):
    return crud.get_print_request(session, request_id)


@router.put("/{request_id}", response_model=PrintRequestRead)
@router.patch("/{request_id}", response_model=PrintRequestRead)
def update_print_request(
    request_id: int,
    data: PrintRequestUpdate,
    session: Session = Depends(get_session),
):
    return crud.update_print_request(session, request_id, data)


@router.delete("/{request_id}", status_code=204)
def delete_print_request(request_id: int, session: Session = Depends(get_session)):
    crud.delete_print_request(session, request_id)
