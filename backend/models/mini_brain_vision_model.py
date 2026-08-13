"""MB-15: Vision Model Integration & Human-in-the-Loop Annotation
Center API schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    vision_session_public_id: str = Field(min_length=1, max_length=100)
    language_session_public_id: str | None = Field(default=None, max_length=100)
    provider_key: str = Field(min_length=1, max_length=100)


class ProviderSelectionRequest(DomainModel):
    model_path: str | None = Field(default=None, max_length=1000)
    mmproj_path: str | None = Field(default=None, max_length=1000)
    context_length: int = Field(default=2048, ge=256, le=65536)


class OcrCrossValidationRequest(DomainModel):
    dataset_text: str | None = Field(default=None, max_length=200000)


class ProviderStatusRequest(DomainModel):
    status: str = Field(min_length=1, max_length=20)


class ReviewPredictionRequest(DomainModel):
    action: str = Field(min_length=1, max_length=40)
    prediction_public_id: str | None = Field(default=None, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)
