"""MB-19: Evaluation & Benchmark Center API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    topic: str = Field(min_length=1, max_length=300)


class CollectDatasetsRequest(DomainModel):
    dataset_session_public_ids: list[str] = Field(min_length=1, max_length=50)


class CollectRagSessionsRequest(DomainModel):
    rag_session_public_ids: list[str] = Field(default_factory=list, max_length=50)


class CollectTrainingPackagesRequest(DomainModel):
    training_package_session_public_ids: list[str] = Field(default_factory=list, max_length=50)


class RegressionComparisonRequest(DomainModel):
    baseline_session_public_id: str | None = Field(default=None, max_length=100)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)
