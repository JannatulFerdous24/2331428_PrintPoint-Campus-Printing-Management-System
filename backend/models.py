from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


class PrintType(str, Enum):
    black_and_white = "Black & White"
    color = "Color"


class RequestStatus(str, Enum):
    pending = "Pending"
    processing = "Processing"
    ready = "Ready"
    collected = "Collected"
    rejected = "Rejected"


# Valid status transitions: key -> allowed next statuses
VALID_TRANSITIONS: dict[RequestStatus, list[RequestStatus]] = {
    RequestStatus.pending: [RequestStatus.processing, RequestStatus.rejected],
    RequestStatus.processing: [RequestStatus.ready, RequestStatus.rejected],
    RequestStatus.ready: [RequestStatus.collected, RequestStatus.rejected],
    RequestStatus.collected: [],
    RequestStatus.rejected: [],
}


class PrintRequest(SQLModel, table=True):
    __tablename__ = "print_requests"

    id: Optional[int] = Field(default=None, primary_key=True)
    student_name: str = Field(index=True, min_length=1, max_length=200)
    document_name: str = Field(min_length=1, max_length=500)
    copies: int = Field(ge=1, le=999)
    print_type: PrintType = Field(default=PrintType.black_and_white)
    status: RequestStatus = Field(default=RequestStatus.pending)
    notes: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
