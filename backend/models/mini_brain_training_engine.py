"""MB-22: Real Training Execution Engine API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class CreateJobRequest(DomainModel):
    topic: str = Field(min_length=1, max_length=300)
    training_package_session_public_id: str = Field(min_length=1, max_length=100)
    release_governance_session_public_id: str = Field(min_length=1, max_length=100)
    execution_mode: str = Field(default="simulation", min_length=1, max_length=20)


class AuthorizeRequest(DomainModel):
    authorization_reason: str = Field(min_length=1, max_length=2000)


class StreamMetricRequest(DomainModel):
    step: int = Field(ge=0)
    epoch: int = Field(ge=0)


class SaveCheckpointRequest(DomainModel):
    step: int = Field(ge=0)
    epoch: int = Field(ge=0)
