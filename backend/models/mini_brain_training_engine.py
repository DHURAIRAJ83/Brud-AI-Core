"""MB-22: Real Training Execution Engine API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CreateJobRequest(DomainModel):
    topic: str = Field(min_length=1, max_length=300)
    training_package_session_public_id: str = Field(min_length=1, max_length=100)
    release_governance_session_public_id: str = Field(min_length=1, max_length=100)
    execution_mode: str = Field(default="simulation", min_length=1, max_length=20)
    # Phase 2.7E: which real Core Model Version this job trains. Optional
    # here at the schema level (existing simulation/cpu-mode jobs never
    # needed one) -- the service layer requires and validates it only when
    # execution_mode='gpu', mirroring PretrainingService's own real
    # eligibility rule rather than a new Pydantic-level requirement that
    # would need to vary by another field's value.
    core_model_version_public_id: str | None = Field(default=None, max_length=100)
    # Phase 2.7F: which real dataset version this job trains against --
    # same optionality rule as above (required only for execution_mode='gpu').
    dataset_version_public_id: str | None = Field(default=None, max_length=100)


class AuthorizeRequest(DomainModel):
    authorization_reason: str = Field(min_length=1, max_length=2000)


class ReserveRuntimeRequest(DomainModel):
    # Phase 2.7E: real training inputs for a real (execution_mode='gpu')
    # job's reserve-runtime stage -- required only for that mode (service-
    # validated). MB-22 has no dataset-to-token-block pipeline of its own
    # yet (a documented, separate gap -- see the Phase 2.7E report), so a
    # real caller supplies already-tokenized blocks explicitly, exactly as
    # `TorchTrainingAdapter` itself has always required via its
    # constructor/`job_context`. Never used by simulation/cpu-mode jobs.
    train_blocks: list[list[int]] | None = None
    validation_blocks: list[list[int]] | None = None
    configuration_label: str | None = Field(default=None, max_length=200)


class StreamMetricRequest(DomainModel):
    step: int = Field(ge=0)
    epoch: int = Field(ge=0)


class SaveCheckpointRequest(DomainModel):
    step: int = Field(ge=0)
    epoch: int = Field(ge=0)
