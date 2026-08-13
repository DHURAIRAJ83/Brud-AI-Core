"""MB-21: External AI Evaluation Gateway API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    topic: str = Field(min_length=1, max_length=300)
    purpose: str = Field(min_length=1, max_length=60)
    dataset_session_public_ids: list[str] = Field(default_factory=list, max_length=50)
    rag_session_public_id: str | None = Field(default=None, max_length=100)


class AuthorizeRequest(DomainModel):
    authorization_note: str = Field(min_length=1, max_length=2000)


class SanitizeRequest(DomainModel):
    admin_stated_need: str = Field(default="", max_length=4000)


class SelectProvidersRequest(DomainModel):
    requested_provider_keys: list[str] = Field(min_length=1, max_length=20)


class DispatchRequest(DomainModel):
    timeout_seconds: float = Field(default=30.0, ge=1.0, le=120.0)
    retain_raw_responses: bool = Field(default=False)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)
