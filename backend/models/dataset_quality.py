"""Phase 6 dataset quality request models."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class QualityAssessRequest(DomainModel):
    force: bool = False


class BulkQualityAssessRequest(DomainModel):
    status: str | None = None
    language: str | None = None
    record_type: str | None = None
    source_public_id: str | None = None
    min_updated_at: str | None = None
    max_records: int = Field(default=100, ge=1, le=500)


class BulkReviewRequest(DomainModel):
    record_public_ids: list[str] = Field(min_length=1, max_length=500)
    action: str
    comments: str | None = Field(default=None, max_length=4000)
    override_quality: bool = False
    override_comment: str | None = Field(default=None, max_length=4000)


class QualityIssuePublic(DomainModel):
    public_id: str
    issue_code: str
    severity: str
    field_name: str | None
    message: str
    metadata: dict[str, Any]
    created_at: str
