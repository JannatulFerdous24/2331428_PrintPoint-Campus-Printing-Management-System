from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from models import PrintType, RequestStatus


class PrintRequestCreate(BaseModel):
    student_name: str = Field(min_length=1, max_length=200)
    document_name: str = Field(min_length=1, max_length=500)
    copies: int = Field(ge=1, le=999)
    print_type: PrintType = PrintType.black_and_white
    notes: Optional[str] = Field(default=None, max_length=1000)


class PrintRequestUpdate(BaseModel):
    student_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    document_name: Optional[str] = Field(default=None, min_length=1, max_length=500)
    copies: Optional[int] = Field(default=None, ge=1, le=999)
    print_type: Optional[PrintType] = None
    status: Optional[RequestStatus] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


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

    model_config = {"from_attributes": True}
