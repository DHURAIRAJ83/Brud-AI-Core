"""MB-31G: Mini Brain Health Snapshot -- a single, consolidated,
read-only diagnostics view composed entirely from existing
RuntimeManagerService/MiniBrainLlmRuntimeService data. No new model
loading, no new network calls, no new scoring logic -- every value is
either read directly from an existing service or derived via an
existing pure function (`ram_guard.check_load_safety`,
`benchmark_scorer` rating thresholds, `model_catalog`'s own curated
`tamil_support` field).
"""

from __future__ import annotations

from backend.core.validation import DomainModel


class BilingualLabel(DomainModel):
    en: str
    ta: str


class MiniBrainHealthSnapshot(DomainModel):
    backend_type: str
    model_loaded: bool
    model_id: str | None = None
    configured_model_path_masked: str | None = None
    available_ram_gb: float
    projected_free_ram_gb: float | None = None
    benchmark_rating: str | None = None
    tokens_per_second: float | None = None
    external_provider_enabled: bool
    external_provider_name: str | None = None
    tamil_quality_status: str | None = None
    english_quality_status: str | None = None
    last_benchmark_at: str | None = None
    next_action: BilingualLabel
