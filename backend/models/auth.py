"""Safe authentication transport and domain schemas."""

from datetime import datetime

from pydantic import Field, field_validator

from backend.core.validation import DomainModel, PublicIdModel


class LoginRequest(DomainModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


class AdminPublic(PublicIdModel):
    username: str
    display_name: str


class AdminListItem(AdminPublic):
    status: str


class SessionPublic(DomainModel):
    expires_at: datetime
    last_used_at: datetime


class AuthenticatedResponse(DomainModel):
    authenticated: bool = True
    admin: AdminPublic


class CurrentAdminResponse(AuthenticatedResponse):
    session: SessionPublic


class AdminCreate(DomainModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("password")
    @classmethod
    def reject_common_password(cls, value: str) -> str:
        if value.lower() in {"password", "password123", "administrator", "admin123456"}:
            raise ValueError("password is too common")
        return value
