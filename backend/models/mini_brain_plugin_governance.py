"""MB-24: Plugin & Tool Runtime Governance Center API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class PluginManifestPayload(DomainModel):
    plugin_id: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    version: str = Field(min_length=1, max_length=200)
    author: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=2000)
    entrypoint: str = Field(min_length=1, max_length=500)
    requested_scopes: list[str] = Field(default_factory=list, max_length=20)
    allowed_domains: list[str] = Field(default_factory=list, max_length=20)
    filesystem_roots: list[str] = Field(default_factory=list, max_length=10)
    ui_components: list[str] = Field(default_factory=list, max_length=20)
    local_storage_usage: bool = False
    cloud_storage_usage: bool = False
    minimum_brud_version: str = Field(default="", max_length=50)
    signature_placeholder: str = Field(default="", max_length=500)
    homepage: str = Field(default="", max_length=500)
    support_url: str = Field(default="", max_length=500)


class RegisterPluginRequest(DomainModel):
    manifest: PluginManifestPayload
    source: str = Field(default="manual_upload", max_length=50)


class EvaluatePermissionRequest(DomainModel):
    scope_key: str = Field(min_length=1, max_length=100)
    is_public_chat: bool = False
    user_id_hash: str | None = Field(default=None, max_length=100)


class RequestConsentRequest(DomainModel):
    scope_key: str = Field(min_length=1, max_length=100)
    raw_user_identity: str = Field(min_length=1, max_length=200)
    consent_given: bool
    ttl_seconds: float | None = Field(default=None, gt=0, le=31_536_000)


class GrantPermissionRequest(DomainModel):
    scope_key: str = Field(min_length=1, max_length=100)
    user_id_hash: str | None = Field(default=None, max_length=100)


class RevokePermissionRequest(DomainModel):
    scope_key: str = Field(min_length=1, max_length=100)


class IssueTokenRequest(DomainModel):
    scope_keys: list[str] = Field(min_length=1, max_length=20)
    raw_user_identity: str = Field(min_length=1, max_length=200)
    raw_session_identity: str = Field(min_length=1, max_length=200)
    ttl_seconds: float = Field(default=300.0, gt=0, le=3600)


class RuntimeEventRequest(DomainModel):
    event_type: str = Field(min_length=1, max_length=100)
    message: str = Field(default="", max_length=1000)
    metadata: dict = Field(default_factory=dict)
