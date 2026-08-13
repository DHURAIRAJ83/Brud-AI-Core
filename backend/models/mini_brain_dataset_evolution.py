"""MB-11: Dataset Evolution & Knowledge Factory API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CreateSessionRequest(DomainModel):
    dataset_source_public_id: str = Field(min_length=1, max_length=100)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)


class RagAdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=40)


class RunRagEvaluationRequest(DomainModel):
    rag_sandbox_experiment_public_id: str = Field(min_length=1, max_length=100)
    retrieval_run_public_id: str = Field(min_length=1, max_length=100)
    generation_assignment_public_id: str = Field(min_length=1, max_length=100)
