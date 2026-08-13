"""MB-25: Secure Plugin Execution Runtime API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel

MAX_ARGUMENTS_FIELDS = 50


class ExecuteRequest(DomainModel):
    plugin_public_id: str = Field(min_length=1, max_length=100)
    scope_key: str = Field(min_length=1, max_length=100)
    arguments: dict = Field(default_factory=dict)
    execution_token: dict = Field(min_length=1)
    timeout_seconds: float = Field(default=5.0, gt=0, le=30.0)


class PublicExecuteRequest(DomainModel):
    plugin_public_id: str = Field(min_length=1, max_length=100)
    scope_key: str = Field(min_length=1, max_length=100)
    arguments: dict = Field(default_factory=dict)
    raw_user_identity: str = Field(min_length=1, max_length=200)
    execution_token: dict = Field(min_length=1)


class RuntimeEventRequest(DomainModel):
    event_type: str = Field(min_length=1, max_length=100)
    message: str = Field(default="", max_length=1000)
    metadata: dict = Field(default_factory=dict)
