"""MB-27: Secrets & Provider Settings API schemas.

`SetProviderSecretRequest.value` is the ONLY field anywhere in this
file permitted to carry secret plaintext -- and it exists solely on
the request side. No response model in this file defines a field named
`value`, `encrypted_value`, `api_key`, `secret_value`, or any other
plaintext-shaped name; this asymmetry is exactly what
`test_mini_brain_provider_settings_safety.py` checks structurally via
AST field-name inspection.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from backend.core.validation import DomainModel

PROVIDER_KEYS = Literal["openrouter", "openai", "anthropic", "gemini", "faster_whisper", "coqui_tts", "local_llm"]


class CreateProviderSettingRequest(DomainModel):
    provider_key: PROVIDER_KEYS
    enabled: bool = False
    config: dict = Field(default_factory=dict)


class UpdateProviderSettingRequest(DomainModel):
    config: dict | None = None


class SetProviderSecretRequest(DomainModel):
    secret_name: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=8000)


class TestConnectionRequest(DomainModel):
    secret_name: str = "api_key"
    timeout_seconds: float = Field(default=10.0, ge=1.0, le=30.0)


class ImportSettingsMetadataRequest(DomainModel):
    providers: list[dict]


class MaskedSecretResponse(DomainModel):
    secret_name: str
    masked_indicator: str
    is_set: bool
    updated_at: str | None = None


class ProviderSettingResponse(DomainModel):
    public_id: str
    provider_key: str
    provider_type: str
    enabled: bool
    config: dict
    secrets: list[MaskedSecretResponse]
    capability_flags: dict
    health: str
    updated_at: str | None = None


class ConnectionTestResponse(DomainModel):
    provider_key: str
    status: str
    latency_ms: float
    error_message: str | None = None


class DiagnosticsResponse(DomainModel):
    encryption_available: bool
    missing_encryption_key: bool
    configured_provider_count: int
    enabled_provider_count: int
    provider_health: list[dict]
    unavailable_providers: list[str]
