"""
/api/print-requests - the Mid Project endpoints (same paths, same fields) with
the Final Project's authorization rules from rbac.py:

  list    students: own + their groups' requests   admins: all
          search/filters: q, status, print_type, group_id, created_from/to,
          has_document, sort (newest|oldest); total in the X-Total-Count header
  read    owner, group members, admins              others: 404
  create  anyone; inside a group needs can_create
  update  fields: owner or can_edit member, only while Pending
          status: admins only (staff), valid transitions only,
                  rejecting requires a reason (5-500 characters)
  delete  request owner or group owner (admins use /api/admin moderation)
  document  upload/replace (PUT): same rule as editing (Pending only)
            download link (GET): anyone who can view the request
"""

from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status
from sqlmodel import Session, select

import crud
from audit import log_event
from auth.dependencies import get_current_user
from database import get_session
from documents import MAX_UPLOAD_BYTES, extension_of, storage_key, validate_document
from models import PrintRequest, PrintRequestStatusHistory, PrintType, RequestStatus, User
from rbac import (
    GroupPerm,
    Permission,
    forbidden,
    get_membership,
    get_visible_request,
    has_permission,
    load_group,
    request_permissions,
    visible_group_ids,
)
from schemas import (
    AssigneeUpdate,
    DocumentLink,
    PrintRequestCreate,
    PrintRequestRead,
    PrintRequestUpdate,
    StatusHistoryRead,
)
from storage import SIGNED_URL_SECONDS, Storage, StorageError, delete_quietly, get_optional_storage, get_storage

# Every endpoint in this router requires a valid, logged-in user (401 otherwise).
router = APIRouter(
    prefix="/api/print-requests",
    tags=["print-requests"],
    dependencies=[Depends(get_current_user)],
)


def to_read(session: Session, user: User, pr: PrintRequest, perms: Optional[dict] = None) -> PrintRequestRead:
    out = PrintRequestRead.model_validate(pr)
    out.permissions = perms or request_permissions(session, user, pr)
    out.rejection_reason = crud.rejection_reason(session, pr)
    out.has_document = pr.storage_path is not None
    return out


def list_filters(
    q: Optional[str] = Query(default=None, max_length=100, description="ID, student, document, file or owner email"),
    status: Optional[RequestStatus] = Query(default=None),
    print_type: Optional[PrintType] = Query(default=None),
    group_id: Optional[int] = Query(default=None),
    created_from: Optional[datetime] = Query(default=None),
    created_to: Optional[datetime] = Query(default=None),
    has_document: Optional[bool] = Query(default=None),
) -> dict:
    return dict(q=q, status=status, print_type=print_type, group_id=group_id,
                created_from=created_from, created_to=created_to, has_document=has_document)


@router.post("", response_model=PrintRequestRead, status_code=201)
def create_print_request(
    data: PrintRequestCreate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if data.group_id is not None:
        load_group(session, user, data.group_id, GroupPerm.CREATE)  # 404 / 403
    pr = crud.create_print_request(session, data, owner_id=user.id, request=request)
    return to_read(session, user, pr)


@router.get("", response_model=list[PrintRequestRead])
def list_print_requests(
    response: Response,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    sort: Literal["newest", "oldest"] = Query(default="newest"),
    filters: dict = Depends(list_filters),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if has_permission(user, Permission.REQUEST_READ_ALL):
        visible_to = None  # staff/admin oversight: everything
    else:
        if filters["group_id"] is not None:
            load_group(session, user, filters["group_id"], GroupPerm.VIEW)  # 404 for non-members
        visible_to = (user.id, visible_group_ids(session, user))
    conds = crud.request_filters(visible_to=visible_to, **filters)
    rows, total = crud.query_print_requests(session, conds, skip=skip, limit=limit, sort=sort)
    response.headers["X-Total-Count"] = str(total)
    return [to_read(session, user, pr) for pr in rows]


@router.get("/{request_id}", response_model=PrintRequestRead)
def get_print_request(request_id: int, session: Session = Depends(get_session),
                      user: User = Depends(get_current_user)):
    pr, perms = get_visible_request(session, user, request_id)
    return to_read(session, user, pr, perms)


@router.get("/{request_id}/history", response_model=list[StatusHistoryRead])
def get_status_history(request_id: int, session: Session = Depends(get_session),
                       user: User = Depends(get_current_user)):
    pr, _ = get_visible_request(session, user, request_id)
    rows = session.exec(
        select(PrintRequestStatusHistory, User.full_name)
        .join(User, User.id == PrintRequestStatusHistory.changed_by_id, isouter=True)
        .where(PrintRequestStatusHistory.print_request_id == pr.id)
        .order_by(PrintRequestStatusHistory.changed_at, PrintRequestStatusHistory.id)
    ).all()
    out = []
    for h, name in rows:
        item = StatusHistoryRead.model_validate(h)
        item.changed_by_name = name
        out.append(item)
    return out


@router.put("/{request_id}", response_model=PrintRequestRead)
@router.patch("/{request_id}", response_model=PrintRequestRead)
def update_print_request(
    request_id: int,
    data: PrintRequestUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    pr, perms = get_visible_request(session, user, request_id)
    changes = data.model_dump(exclude_unset=True)
    status_change = "status" in changes and changes["status"] != pr.status
    # "reason" belongs to the status change (staff), not to the request's own fields.
    field_changes = {k for k in changes if k not in ("status", "reason")}

    if status_change and not perms["change_status"]:
        raise forbidden("Only print-shop staff (admins) can change the status of a request")
    if field_changes and not perms["edit"]:
        if pr.status != RequestStatus.pending:
            raise forbidden("Only Pending requests can be edited")
        raise forbidden("You do not have permission to edit this request")

    pr = crud.update_print_request(session, pr, data, actor=user, request=request)
    return to_read(session, user, pr)


# ------------------------------------------------------------------ documents

@router.put("/{request_id}/document", response_model=PrintRequestRead)
def upload_document(
    request_id: int,
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
):
    pr, perms = get_visible_request(session, user, request_id)
    if not perms["edit"]:
        if pr.status != RequestStatus.pending:
            raise forbidden("Documents can only be changed while the request is Pending")
        raise forbidden("You do not have permission to change this request's document")

    data = file.file.read(MAX_UPLOAD_BYTES + 1)  # never reads more than limit + 1 byte
    name, content_type = validate_document(file.filename or "", data)

    key = storage_key(pr.id, extension_of(name))
    try:
        storage.upload(key, data, content_type)
    except StorageError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Could not store the document. Please try again.")

    old_key = pr.storage_path
    pr.storage_path, pr.original_filename = key, name
    pr.content_type, pr.file_size_bytes = content_type, len(data)
    pr.uploaded_at = pr.updated_at = datetime.now(timezone.utc)
    session.add(pr)
    log_event(session, "request.document_replace" if old_key else "request.document_upload",
              request=request, actor_id=user.id, target_type="print_request", target_id=pr.id,
              details={"filename": name, "size": len(data), "content_type": content_type})
    try:
        session.commit()
    except Exception:
        session.rollback()
        delete_quietly(storage, key)  # keep storage and database consistent
        raise
    delete_quietly(storage, old_key)
    session.refresh(pr)
    return to_read(session, user, pr)


@router.get("/{request_id}/document", response_model=DocumentLink)
def document_link(
    request_id: int,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
    storage: Storage = Depends(get_storage),
):
    pr, _ = get_visible_request(session, user, request_id)  # 404 unless allowed to view
    if not pr.storage_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="This request has no document")
    try:
        url = storage.signed_url(pr.storage_path, pr.original_filename or "document")
    except StorageError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Could not open the document. Please try again.")
    log_event(session, "request.document_download", request=request, actor_id=user.id,
              target_type="print_request", target_id=pr.id)
    session.commit()
    return DocumentLink(url=url, expires_in=SIGNED_URL_SECONDS, filename=pr.original_filename or "document")


@router.patch("/{request_id}/assignee", response_model=PrintRequestRead)
def set_assignee(
    request_id: int,
    data: AssigneeUpdate,
    request: Request,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
):
    pr, perms = get_visible_request(session, user, request_id)
    if pr.group_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Only group requests can be assigned")
    if not perms["assign"]:
        raise forbidden("You do not have permission to assign requests in this group")
    if data.assignee_id is not None:
        group, _ = load_group(session, user, pr.group_id, GroupPerm.ASSIGN)
        is_member = (data.assignee_id == group.owner_id
                     or get_membership(session, group.id, data.assignee_id) is not None)
        if not is_member:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                detail="The assignee must be a member of the group")
    old = pr.assignee_id
    pr.assignee_id = data.assignee_id
    session.add(pr)
    log_event(session, "request.assign", request=request, actor_id=user.id,
              target_type="print_request", target_id=pr.id,
              details={"from": old, "to": data.assignee_id})
    session.commit()
    session.refresh(pr)
    return to_read(session, user, pr)


@router.delete("/{request_id}", status_code=204)
def delete_print_request(request_id: int, request: Request,
                         session: Session = Depends(get_session),
                         user: User = Depends(get_current_user),
                         storage: Optional[Storage] = Depends(get_optional_storage)):
    pr, perms = get_visible_request(session, user, request_id)
    if not perms["delete"]:
        raise forbidden("Only the request owner or the group owner can delete this request")
    delete_quietly(storage, crud.delete_print_request(session, pr, actor=user, request=request))
