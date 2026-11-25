"""Request/response shapes for the authentication and account endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from models import UserRole


class SignupRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    full_name: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("full_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Full name is required")
        return v


class LoginRequest(BaseModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=1, max_length=128)


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: UserRead


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    email: Optional[EmailStr] = Field(default=None, max_length=255)
    # Required only when changing the email address.
    current_password: Optional[str] = Field(default=None, max_length=128)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


class SessionRead(BaseModel):
    id: int
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool
