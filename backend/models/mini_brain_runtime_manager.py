"""MB-30: Production Runtime Manager & One-Click Local Model Lifecycle
API schemas. No field in any response model here is secret-shaped --
this phase never stores or returns provider secrets (it only ever
reads MB-27's masked provider list to resolve external-fallback
availability).
"""

from __future__ import annotations

from pydantic import Field

from backend.core.validation import DomainModel


class ModelIdRequest(DomainModel):
    model_id: str = Field(min_length=1, max_length=200)


class LoadModelRequest(DomainModel):
    model_id: str = Field(min_length=1, max_length=200)
    context_length: int = Field(default=2048, ge=256, le=32_768)
    max_tokens: int = Field(default=512, ge=16, le=4096)
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    threads: int = Field(default=4, ge=1, le=64)


class BenchmarkModelRequest(DomainModel):
    model_id: str = Field(min_length=1, max_length=200)
    prompt: str = Field(default="Say hello in one short sentence.", max_length=2000)


# -- response models (post-audit remediation D2) ------------------------------------------------
# Every field below was verified against a real, live service call before being written --
# DomainModel's `extra="forbid"` means an unverified extra/missing field would 500 the route.


class BilingualLabel(DomainModel):
    en: str
    ta: str


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


class CatalogModelEntry(DomainModel):
    model_id: str
    display_name: str
    family: str
    quantization: str
    file_name: str
    download_url: str
    sha256: str
    expected_size_bytes: int
    recommended_ram_gb: int | float
    expected_ram_usage_gb: float
    tamil_support: str
    speed_tier: str
    tier: str


class CatalogResponse(DomainModel):
    models: list[CatalogModelEntry]


class InstallationResponse(DomainModel):
    public_id: str
    model_name: str
    family: str | None = None
    quantization: str | None = None
    file_name: str
    install_path: str
    file_size_bytes: int | None = None
    sha256: str | None = None
    status: str
    installed_at: str | None = None
    removed_at: str | None = None
    created_at: str
    updated_at: str


class InstalledListResponse(DomainModel):
    items: list[InstallationResponse]


class VerifyResponse(DomainModel):
    matches: bool
    actual_sha256: str
    expected_sha256: str
    message_en: str
    message_ta: str


class RuntimeRowResponse(DomainModel):
    public_id: str
    model_name: str
    loaded: bool
    backend: str
    context_length: int | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    threads: int | None = None
    load_time_ms: float | None = None
    last_used_at: str | None = None
    peak_ram_mb: float | None = None
    tokens_per_second: float | None = None
    created_at: str


class RuntimeStatusResponse(DomainModel):
    loaded: bool
    current_model: RuntimeRowResponse | None = None
    installed_count: int
    installed_models: list[InstallationResponse]
    hardware: HardwareProbeResponse | None = None


class BenchmarkResponse(DomainModel):
    rating: str
    rating_label: BilingualLabel
    load_time_ms: float
    first_token_latency_ms: float
    tokens_per_second: float
    peak_ram_mb: float
    runtime_row: RuntimeRowResponse
    reply_error: str | None = None


class RuntimeEventResponse(DomainModel):
    public_id: str
    model_name: str | None = None
    event_type: str
    admin_id: str | None = None
    created_at: str
    detail: dict


class RuntimeEventListResponse(DomainModel):
    items: list[RuntimeEventResponse]


class RuntimeMemoryResponse(DomainModel):
    public_id: str
    model_name: str | None = None
    event_type: str
    admin_id: str | None = None
    created_at: str


class RuntimeMemoryListResponse(DomainModel):
    items: list[RuntimeMemoryResponse]


class FallbackStatusResponse(DomainModel):
    step: int
    backend: str
    reason: str


class ModelStatusSummary(DomainModel):
    installed_count: int
    installed_models: list[InstallationResponse]


class LoadState(DomainModel):
    loaded: bool
    current_model: RuntimeRowResponse | None = None


class LastBenchmarkSummary(DomainModel):
    tokens_per_second: float | None = None
    peak_ram_mb: float | None = None
    load_time_ms: float | None = None


class BenchmarkAvailability(DomainModel):
    has_benchmark_data: bool
    last_benchmark: LastBenchmarkSummary | None = None


class StoragePaths(DomainModel):
    allowed_model_dir: str


class RuntimeManagerDiagnosticsResponse(DomainModel):
    hardware: HardwareProbeResponse
    model_status: ModelStatusSummary
    load_state: LoadState
    benchmark_availability: BenchmarkAvailability
    storage_paths: StoragePaths
    fallback_state: FallbackStatusResponse
