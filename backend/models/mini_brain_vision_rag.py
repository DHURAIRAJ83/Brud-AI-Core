"""MB-17: Vision RAG & Multimodal Retrieval Center API schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    multimodal_dataset_session_public_id: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=2000)


class CorrectResponseRequest(DomainModel):
    action: str = Field(min_length=1, max_length=40)
    payload: dict[str, Any] = Field(default_factory=dict)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)
