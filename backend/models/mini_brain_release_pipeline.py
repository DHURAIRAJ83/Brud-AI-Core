"""MB-07: Release Pipeline API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class ReleaseSessionCreateRequest(DomainModel):
    core_model_version_public_id: str = Field(min_length=1, max_length=100)
    pretraining_checkpoint_public_id: str = Field(min_length=1, max_length=100)
    model_release_family_public_id: str = Field(min_length=1, max_length=100)
    target_quantizations: list[str] = Field(min_length=1, max_length=10)
    dataset_version_public_id: str | None = None
    model_evaluation_run_public_id: str | None = None


class CreateReleaseVersionRequest(DomainModel):
    version: str = Field(min_length=1, max_length=40)
    prerelease_label: str | None = Field(default=None, max_length=40)


class EvaluateRollbackRequest(DomainModel):
    target_version: str = Field(min_length=1, max_length=40)


class ExecuteRollbackRequest(DomainModel):
    target_release_public_id: str = Field(min_length=1, max_length=100)
    reason: str = Field(default="", max_length=2000)


class AdminReviewRequest(DomainModel):
    decision: str = Field(min_length=1, max_length=20)


class ActivateRequest(DomainModel):
    quantization_level: str = Field(min_length=1, max_length=20)
