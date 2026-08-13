"""MB-06: Learning Supervisor API schemas."""

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class LearningSessionCreateRequest(DomainModel):
    dataset_source_public_id: str = Field(min_length=1, max_length=100)
    hyperparameter_profile: str = Field(default="default", min_length=1, max_length=40)


class DatasetDecisionRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=20)


class RagDecisionRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=20)


class RunRagEvaluationRequest(DomainModel):
    rag_sandbox_experiment_public_id: str = Field(min_length=1, max_length=100)
    retrieval_run_public_id: str = Field(min_length=1, max_length=100)
    generation_assignment_public_id: str = Field(min_length=1, max_length=100)


class SubmitTrainingRequestRequest(DomainModel):
    name: str = Field(min_length=1, max_length=200)
    dataset_version_public_id: str = Field(min_length=1, max_length=100)
    tokenizer_version_public_id: str = Field(min_length=1, max_length=100)
    core_model_version_public_id: str = Field(min_length=1, max_length=100)
    hyperparameter_profile: str | None = None


class RunBenchmarkRequest(DomainModel):
    model_evaluation_fixture_set_public_id: str = Field(min_length=1, max_length=100)
    candidate_core_model_version_public_id: str = Field(min_length=1, max_length=100)
    generation_configuration: dict[str, Any] = Field(default_factory=dict)


class CompareModelsRequest(DomainModel):
    previous_benchmark_run_public_id: str = Field(min_length=1, max_length=100)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=20)


class ReleaseCandidateRequest(DomainModel):
    checkpoint_public_id: str = Field(min_length=1, max_length=100)
    override_comment: str | None = Field(default=None, max_length=2000)
