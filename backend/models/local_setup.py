"""MB-29: Local Model Auto-Setup & Provider Configuration Center API
schemas. `SaveProviderRequest.api_key` is the only field anywhere in
this file permitted to carry secret plaintext -- request-side only,
mirroring MB-27's own `SetProviderSecretRequest.value` discipline
exactly. No response model in this file ever echoes it back.
"""

from __future__ import annotations

from pydantic import Field

from backend.core.validation import DomainModel


class SaveLocalModelRequest(DomainModel):
    model_path: str | None = None
    context_length: int = Field(default=2048, ge=256, le=32_768)
    max_tokens: int = Field(default=512, ge=16, le=4096)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    threads: int = Field(default=4, ge=1, le=64)
    additional_model_dirs: list[str] | None = None


class SaveProviderRequest(DomainModel):
    provider_key: str
    api_key: str | None = Field(default=None, max_length=8000)
    model: str | None = None
    enabled: bool = False


# -- response models (post-audit remediation D2) ------------------------------------------------
# Every field below was verified against a real, live service call before being written --
# DomainModel's `extra="forbid"` means an unverified extra/missing field would 500 the route.


class BilingualLabel(DomainModel):
    en: str
    ta: str


class HardwareHealthResponse(DomainModel):
    health: str
    ram_tier: str | None = None
    disk_free_gb: float | None = None
    local_model_configured: bool
    local_model_available: bool


class HardwareProbeResponse(DomainModel):
    total_ram_gb: float
    available_ram_gb: float
    cpu_cores: int
    cpu_threads: int
    architecture: str
    os_name: str
    disk_free_gb: float
    python_version: str
    recommended_ram_tier: str
    psutil_available: bool


class HardwareSummaryResponse(HardwareProbeResponse):
    health: HardwareHealthResponse


class ScannedModelEntry(DomainModel):
    filename: str
    absolute_path: str
    size_gb: float
    modified_at: float
    inferred_family: str | None = None
    inferred_quantization: str | None = None
    inferred_params: float | None = None


class ScanModelsResponse(DomainModel):
    items: list[ScannedModelEntry]
    scanned_directories: list[str]


class RecommendedModelEntry(DomainModel):
    model_name: str
    quantization: str
    params_billions: float
    expected_ram_usage_gb: float
    expected_speed: BilingualLabel
    best_for: BilingualLabel
    tamil_support: BilingualLabel
    english_support: BilingualLabel
    coding_support: BilingualLabel
    offline_support: BilingualLabel
    recommended_for_brud_admin: BilingualLabel


class RecommendationsResponse(DomainModel):
    ram_tier: str
    below_minimum_catalog_tier: bool
    models: list[RecommendedModelEntry]
    top_recommendation: RecommendedModelEntry | None = None


class ProviderCatalogEntry(DomainModel):
    provider_key: str
    recommended_models: list[str]
    context_window: int
    reasoning_level: BilingualLabel
    cost_hint: BilingualLabel
    coding_quality: BilingualLabel
    tamil_quality: BilingualLabel


class ProviderCatalogResponse(DomainModel):
    providers: list[ProviderCatalogEntry]


class SetupGuideStep(DomainModel):
    step: int
    title_en: str
    title_ta: str
    body_en: str
    body_ta: str


class SetupGuideResponse(DomainModel):
    steps: list[SetupGuideStep]


class LocalSetupDiagnosticsResponse(DomainModel):
    hardware: HardwareProbeResponse
    scanned_model_count: int
    configured_model_path: str | None = None
    local_model_available: bool
    additional_model_dirs_count: int
    configured_external_providers: list[str]
