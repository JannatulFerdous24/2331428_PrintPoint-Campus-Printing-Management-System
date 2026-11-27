from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from models import PaymentStatus, PrintType, RequestStatus


class PrintRequestCreate(BaseModel):
    student_name: str = Field(min_length=1, max_length=200)
    document_name: str = Field(min_length=1, max_length=500)
    copies: int = Field(ge=1, le=999)
    pages: int = Field(default=1, ge=1, le=1000)  # pages in the document (cost = pages x copies x rate)
    print_type: PrintType = PrintType.black_and_white
    notes: Optional[str] = Field(default=None, max_length=1000)
    # Optional: create the request inside a group (needs can_create in that group).
    group_id: Optional[int] = None


class PrintRequestUpdate(BaseModel):
    student_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    document_name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    copies: Optional[int] = Field(default=None, ge=1, le=999)
    pages: Optional[int] = Field(default=None, ge=1, le=1000)
    print_type: Optional[PrintType] = None
    status: Optional[RequestStatus] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    # Staff note for a status change, saved in the status history.
    # REQUIRED (5-500 characters) when the new status is Rejected.
    reason: Optional[str] = Field(default=None, max_length=500)


class PrintRequestRead(BaseModel):
    id: int
    student_name: str
    document_name: str
    copies: int
    print_type: PrintType
    status: RequestStatus
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    # Added in the Final Project (additive - Mid Project fields above are unchanged)
    owner_id: Optional[int] = None
    group_id: Optional[int] = None
    assignee_id: Optional[int] = None
    # Why staff rejected the request (from the status history); None unless Rejected.
    rejection_reason: Optional[str] = None
    # Uploaded document (metadata only - the private storage key is never sent out).
    has_document: bool = False
    original_filename: Optional[str] = None
    content_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    # Cost (Taka, calculated by the server) and payment tracking.
    pages: int = 1
    total_cost: int = 0
    payment_status: PaymentStatus = PaymentStatus.pending
    paid_at: Optional[datetime] = None
    # What the CURRENT user may do with this request, computed by rbac.py.
    # The UI uses it to show/hide buttons; the server still checks every action.
    permissions: Optional[dict[str, bool]] = None

    model_config = {"from_attributes": True}


class PaymentUpdate(BaseModel):
    payment_status: PaymentStatus


class PricingRead(BaseModel):
    currency: str
    rates_per_page: dict[PrintType, int]


class AssigneeUpdate(BaseModel):
    assignee_id: Optional[int] = None  # None = unassign


class StatusHistoryRead(BaseModel):
    from_status: Optional[RequestStatus]
    to_status: RequestStatus
    changed_by_id: Optional[int]
    changed_by_name: Optional[str] = None
    note: Optional[str]
    changed_at: datetime

    model_config = {"from_attributes": True}


class DocumentLink(BaseModel):
    """Short-lived signed link to the private file (issued only after a permission check)."""
    url: str
    expires_in: int
    filename: str
