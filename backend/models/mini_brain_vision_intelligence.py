"""MB-14: Vision Intelligence & Image Understanding Center API
schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    document_source_public_id: str = Field(min_length=1, max_length=100)
    dataset_source_public_id: str | None = Field(default=None, max_length=100)


class RunOcrCrossValidationRequest(DomainModel):
    dataset_text: str | None = Field(default=None, max_length=200000)
    language_report_status: str | None = Field(default=None, max_length=40)


class RunCaptionRequest(DomainModel):
    admin_caption: str | None = Field(default=None, max_length=5000)


class AnnotateRequest(DomainModel):
    action: str = Field(min_length=1, max_length=40)
    object_public_id: str | None = Field(default=None, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)
