"""Central validation primitives for Phase 2 domain data."""

import re
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LanguageCode(StrEnum):
    TA = "ta"
    EN = "en"
    TANGLISH = "tgl"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class AssignmentKey(StrEnum):
    PUBLIC_CHAT = "public_chat"
    ADMIN_CHAT_TEST = "admin_chat_test"
    ADMIN_ASSISTANT = "admin_assistant"
    TANGLISH_NORMALIZER = "tanglish_normalizer"
    EMBEDDING = "embedding"
    FALLBACK = "fallback"


VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_public_id(value: str) -> str:
    """Accept canonical UUID public identifiers only."""

    parsed = UUID(value)
    if str(parsed) != value.lower():
        raise ValueError("public ID must be a canonical UUID")
    return str(parsed)


def validate_version_label(value: str) -> str:
    if not VERSION_PATTERN.fullmatch(value):
        raise ValueError("invalid version label")
    return value


class DomainModel(BaseModel):
    """Strict base for repository and public domain schemas."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)


class PublicIdModel(DomainModel):
    public_id: str

    @field_validator("public_id")
    @classmethod
    def public_id_is_uuid(cls, value: str) -> str:
        return validate_public_id(value)


QualityScore = Field(default=None, ge=0, le=1)
Progress = Field(default=0, ge=0, le=1)
