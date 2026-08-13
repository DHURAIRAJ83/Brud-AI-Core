"""MB-18: Multimodal Training Pipeline Center API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    topic: str = Field(min_length=1, max_length=300)


class CollectDatasetsRequest(DomainModel):
    dataset_session_public_ids: list[str] = Field(min_length=1, max_length=50)


class CollectRagMemoryRequest(DomainModel):
    rag_session_public_ids: list[str] = Field(default_factory=list, max_length=50)


class PlanSplitsRequest(DomainModel):
    seed: int | None = Field(default=None)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)
