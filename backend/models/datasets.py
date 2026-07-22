"""Phase 3 dataset administration request and response schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel, LanguageCode
from backend.models.domain import (
    DatasetRecordType,
    DatasetSourceStatus,
    DatasetSourceType,
    LicenceStatus,
    ReviewDecision,
)


class ManualSourceCreate(DomainModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    language: LanguageCode
    licence_name: str | None = Field(default=None, max_length=255)
    licence_status: LicenceStatus = LicenceStatus.UNKNOWN
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_type: DatasetSourceType = DatasetSourceType.MANUAL


class SourcePatch(DomainModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    language: LanguageCode | None = None
    licence_name: str | None = Field(default=None, max_length=255)
    licence_status: LicenceStatus | None = None
    status: DatasetSourceStatus | None = None
    metadata: dict[str, Any] | None = None


class RecordCreate(DomainModel):
    source_public_id: str
    record_type: DatasetRecordType
    language: LanguageCode
    instruction: str | None = Field(default=None, max_length=20_000)
    input_text: str | None = Field(default=None, max_length=100_000)
    output_text: str | None = Field(default=None, max_length=100_000)
    normalized_input: str | None = Field(default=None, max_length=100_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RecordPatch(DomainModel):
    record_type: DatasetRecordType | None = None
    language: LanguageCode | None = None
    instruction: str | None = Field(default=None, max_length=20_000)
    input_text: str | None = Field(default=None, max_length=100_000)
    output_text: str | None = Field(default=None, max_length=100_000)
    normalized_input: str | None = Field(default=None, max_length=100_000)
    metadata: dict[str, Any] | None = None


class ReviewRequest(DomainModel):
    decision: ReviewDecision
    comments: str | None = Field(default=None, max_length=4000)


class Page(DomainModel):
    items: list[dict[str, Any]]
    page: int
    page_size: int
    total: int
    total_pages: int
