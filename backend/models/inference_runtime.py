"""Phase 15 controlled inference runtime API request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class RuntimeProfileCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    runtime_type: str = Field(default="local_cpu", max_length=20)
    device: str = Field(default="cpu", max_length=20)
    dtype: str = Field(default="float32", max_length=20)
    maximum_loaded_models: int = Field(default=1, ge=1, le=4)
    maximum_concurrent_requests: int = Field(default=1, ge=1, le=4)
    maximum_context_length: int = Field(ge=8, le=32768)
    maximum_new_tokens: int = Field(ge=1, le=8192)
    request_timeout_seconds: int = Field(default=30, ge=1, le=600)
    idle_unload_seconds: int = Field(default=900, ge=1, le=86400)
    minimum_available_memory_bytes: int = Field(ge=0)
    minimum_available_disk_bytes: int = Field(ge=0)
    resource_policy: dict[str, Any] = Field(default_factory=dict)
    generation_defaults: dict[str, Any] = Field(default_factory=dict)


class RuntimeProfilePatch(DomainModel):
    enabled: bool | None = None
    maximum_new_tokens: int | None = Field(default=None, ge=1, le=8192)
    maximum_context_length: int | None = Field(default=None, ge=8, le=32768)
    request_timeout_seconds: int | None = Field(default=None, ge=1, le=600)
    idle_unload_seconds: int | None = Field(default=None, ge=1, le=86400)
    minimum_available_memory_bytes: int | None = Field(default=None, ge=0)
    minimum_available_disk_bytes: int | None = Field(default=None, ge=0)
    resource_policy: dict[str, Any] | None = None
    generation_defaults: dict[str, Any] | None = None


class RuntimeInstanceCreate(DomainModel):
    runtime_profile_public_id: str


class InstanceLoadRequest(DomainModel):
    release_public_id: str


class CompatibilityAssessRequest(DomainModel):
    runtime_profile_public_id: str


class AssignmentCreate(DomainModel):
    scope: str = Field(min_length=1, max_length=40)
    release_public_id: str
    runtime_profile_public_id: str
    generation_config: dict[str, Any] = Field(default_factory=dict)
    context_policy: dict[str, Any] = Field(default_factory=dict)
    fallback_policy: dict[str, Any] = Field(default_factory=dict)
    canary_percentage: int = Field(default=0, ge=0, le=100)
    start_at: str | None = None
    expire_at: str | None = None
    acknowledge_evaluation_warning: bool = False


class AssignmentPatch(DomainModel):
    release_public_id: str | None = None
    generation_config: dict[str, Any] | None = None
    context_policy: dict[str, Any] | None = None
    fallback_policy: dict[str, Any] | None = None
    canary_percentage: int | None = Field(default=None, ge=0, le=100)


class AssignmentActivateRequest(DomainModel):
    explicit_activation_confirmed: bool = False


class AssignmentApprovalCreate(DomainModel):
    role: str = Field(min_length=1, max_length=20)
    decision: str = Field(min_length=1, max_length=40)
    comment: str = Field(default="", max_length=2000)


class DiagnosticGenerateRequest(DomainModel):
    prompt: str = Field(min_length=1, max_length=4000)
    maximum_new_tokens: int | None = Field(default=None, ge=1, le=8192)


class ChatLabSessionCreate(DomainModel):
    max_turns: int = Field(default=10, ge=1, le=100)
    system_prompt: str = Field(default="", max_length=2000)


class ChatLabMessageCreate(DomainModel):
    message: str = Field(min_length=1, max_length=4000)


class CanaryStartRequest(DomainModel):
    percentage: int = Field(ge=0, le=100)
    max_request_count: int = Field(ge=1, le=1000)


class CanaryExecuteRequest(DomainModel):
    fixture_prompts: list[str] = Field(min_length=1, max_length=30)


class CanaryStopRequest(DomainModel):
    reason: str = Field(default="admin_stop", max_length=200)


class RollbackPreviewRequest(DomainModel):
    target_version_public_id: str
    reason: str = Field(default="", max_length=2000)


class RollbackExecuteRequest(DomainModel):
    target_version_public_id: str
    comment: str = Field(default="", max_length=2000)
