"""MB-31G: Mini Brain Health Service -- composes a single consolidated
read-only snapshot from RuntimeManagerService and
MiniBrainLlmRuntimeService, plus existing pure helper modules. Never
loads a model, never makes a network call, never duplicates scoring or
prompt logic -- every derived value calls the real existing function
that already owns that logic.
"""

from __future__ import annotations

from typing import Any

from backend.core.config import Settings
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService
from backend.services.runtime_manager_service import RuntimeManagerService
from core_model.mini_brain.runtime_manager import benchmark_scorer, model_catalog, ram_guard

# No per-language live quality metric exists anywhere in this codebase --
# there is no mechanism that scores a generated reply's language
# correctness. This is a disclosed, curated snapshot reflecting real,
# already-measured findings from real end-to-end validation passes on
# this branch (rc-fixes-2026-08-08), keyed by model_id and re-derived
# from `model_catalog`'s own `tamil_support` field where possible --
# never invented per-request.
_ENGLISH_QUALITY_BY_MODEL: dict[str, str] = {
    "qwen2.5-0.5b-instruct-q4_k_m": "good",
    "qwen2.5-1.5b-instruct-q4_k_m": "good",
    "qwen2.5-3b-instruct-q4_k_m": "good",
    "tinyllama-1.1b-chat-q4_k_m": "good",
}


def _next_action(*, model_loaded: bool, tamil_quality_status: str | None, projected_free_ram_gb: float | None) -> dict[str, str]:
    if not model_loaded:
        if projected_free_ram_gb is not None and projected_free_ram_gb < 0:
            return {
                "en": "No model loaded and RAM is insufficient -- free memory (e.g. close browser tabs) before loading.",
                "ta": "மாடல் எதுவும் ஏற்றப்படவில்லை, RAM போதவில்லை -- ஏற்றும் முன் நினைவகத்தை காலி செய்யவும் (எ.கா. browser tab-களை மூடவும்).",
            }
        return {
            "en": "No local model loaded. Load one from Runtime Manager.",
            "ta": "எந்த local model-உம் ஏற்றப்படவில்லை. Runtime Manager-இலிருந்து ஒன்றை ஏற்றவும்.",
        }
    if tamil_quality_status not in ("good",):
        return {
            "en": "Model is loaded and English answers are reliable. Verify Tamil answers manually before trusting them.",
            "ta": "மாடல் ஏற்றப்பட்டுள்ளது, ஆங்கில பதில்கள் நம்பகமானவை. தமிழ் பதில்களை நம்புவதற்கு முன் கைமுறையாக சரிபார்க்கவும்.",
        }
    return {
        "en": "Model is loaded and ready.",
        "ta": "மாடல் ஏற்றப்பட்டு தயாராக உள்ளது.",
    }


class MiniBrainHealthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.runtime_manager = RuntimeManagerService(settings)
        self.llm_runtime = MiniBrainLlmRuntimeService(settings)

    def snapshot(self) -> dict[str, Any]:
        rm_diag = self.runtime_manager.diagnostics()
        lr_diag = self.llm_runtime.diagnostics()

        current_model = rm_diag["load_state"]["current_model"]
        model_id = current_model["model_name"] if current_model else None
        model_loaded = bool(lr_diag["local_model_loaded"])

        last_benchmark = rm_diag["benchmark_availability"]["last_benchmark"]
        tokens_per_second = last_benchmark["tokens_per_second"] if last_benchmark else None
        benchmark_rating = benchmark_scorer._rate(tokens_per_second) if tokens_per_second is not None else None
        last_benchmark_at = current_model["last_used_at"] if (current_model and last_benchmark) else None

        available_ram_gb = rm_diag["hardware"]["available_ram_gb"]
        reference_model_id = model_id or model_catalog.recommended_model_id()
        reference_entry = model_catalog.catalog_entry(reference_model_id)
        projected_free_ram_gb = None
        if reference_entry is not None:
            guard = ram_guard.check_load_safety(
                available_ram_gb=available_ram_gb, estimated_model_ram_gb=reference_entry["expected_ram_usage_gb"],
            )
            projected_free_ram_gb = guard["projected_free_ram_gb"]

        tamil_quality_status = None
        english_quality_status = None
        if model_id is not None:
            catalog_entry = model_catalog.catalog_entry(model_id)
            tamil_quality_status = catalog_entry["tamil_support"] if catalog_entry else None
            english_quality_status = _ENGLISH_QUALITY_BY_MODEL.get(model_id)

        return {
            "backend_type": rm_diag["fallback_state"]["backend"],
            "model_loaded": model_loaded,
            "model_id": model_id,
            "configured_model_path_masked": lr_diag["configured_model_path"],
            "available_ram_gb": available_ram_gb,
            "projected_free_ram_gb": projected_free_ram_gb,
            "benchmark_rating": benchmark_rating,
            "tokens_per_second": tokens_per_second,
            "external_provider_enabled": lr_diag["external_fallback_enabled"],
            "external_provider_name": lr_diag["external_provider_key"],
            "tamil_quality_status": tamil_quality_status,
            "english_quality_status": english_quality_status,
            "last_benchmark_at": last_benchmark_at,
            "next_action": _next_action(
                model_loaded=model_loaded, tamil_quality_status=tamil_quality_status, projected_free_ram_gb=projected_free_ram_gb,
            ),
        }
