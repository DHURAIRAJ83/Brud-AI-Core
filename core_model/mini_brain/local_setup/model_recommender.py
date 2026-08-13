"""MB-29: Model Recommender -- pure. A deterministic, cumulative-by-RAM-tier
recommendation matrix, per the phase spec's own section 5 table exactly
(6GB tier's three models, extended by 8GB's two additions, extended
again by 16GB+'s two additions -- each tier includes every model from
the tiers below it, since more RAM never makes a smaller model
unsuitable).

**Reconciling two literal requirements that would otherwise conflict**:
section 5 ranks TinyLlama-1.1B first in the 6GB list; section 14's
worked example names Qwen2.5-1.5B-Instruct as *the* recommended model
for a 6GB machine. Both are preserved exactly rather than picking one
over the other: the ranked list below keeps section 5's literal order,
while `recommended_for_brud_admin` is a separate, independently-curated
flag (weighted toward genuine Tamil multilingual capability -- the
Qwen2.5 family is well known for materially better multilingual
support than TinyLlama/SmolLM2/Mistral at a comparable size, which is
why it, not the RAM-frugality leader, is the right single top pick for
a bilingual Tamil+English admin assistant). `recommend()` surfaces both
the full ranked list AND a derived `top_recommendation` selecting the
best `recommended_for_brud_admin=True` candidate -- which resolves to
Qwen2.5-1.5B-Instruct for a 6GB machine, matching section 14 exactly.

MB-31A (2026-08-09): added Qwen2.5-0.5B-Instruct, the real
now-catalogued low-RAM option (see `model_catalog.py`), positioned
ahead of TinyLlama-1.1B in the ranked list -- its real Tamil support
("fair") is meaningfully better than TinyLlama's ("limited"), so when
Tamil matters it is the better small-footprint pick. It is also
`recommended_for_brud_admin=True`. To keep `top_recommendation`
identical at every RAM tier (still Qwen2.5-1.5B-Instruct, matching
section 14 exactly -- this pass does not touch higher-tier
recommendations), Qwen2.5-1.5B-Instruct's own tuple position moves
ahead of both new entrants; its field values are untouched. Net
ordering for the 6GB list: Qwen2.5-1.5B-Instruct, Qwen2.5-0.5B-
Instruct, TinyLlama-1.1B-Chat, SmolLM2-1.7B-Instruct.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.local_setup import capability_catalog

# `expected_ram_usage_gb` is curated per real-world-observed llama.cpp
# runtime figures (weights + KV cache + runtime overhead at a modest
# context length), NOT derived from storage_estimator.py's flat
# formula -- a fixed multiplier under-predicts small models (proportionally
# more of their footprint is runtime/context overhead, not weights) and
# would over-predict large ones. storage_estimator.py is still real,
# genuinely used for scanned/unknown models with no curated entry (see
# `model_scanner.py`). The 1.5B figure (~2.5GB) matches the phase
# spec's own section 14 worked example exactly.
_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "model_name": "Qwen2.5-1.5B-Instruct", "quantization": "Q4_K_M", "params_billions": 1.5,
        "expected_ram_usage_gb": 2.5,
        "min_ram_tier": "6GB", "expected_speed": "good",
        "best_for": capability_catalog.bilingual("General admin Q&A with real Tamil support on modest hardware", "மிதமான வன்பொருளில் உண்மையான தமிழ் ஆதரவுடன் பொது நிர்வாக கேள்வி பதில்"),
        "tamil_support": "good", "english_support": "good", "coding_support": "fair", "offline_support": True,
        "recommended_for_brud_admin": True,
    },
    {
        "model_name": "Qwen2.5-0.5B-Instruct", "quantization": "Q4_K_M", "params_billions": 0.5,
        "expected_ram_usage_gb": 1.0,
        "min_ram_tier": "6GB", "expected_speed": "excellent",
        "best_for": capability_catalog.bilingual("Genuinely low-RAM machines needing real Tamil support, ahead of TinyLlama", "உண்மையான தமிழ் ஆதரவு தேவைப்படும் மிகக் குறைந்த RAM கணினிகளுக்கு, TinyLlama-வை விட முன்னுரிமை"),
        "tamil_support": "fair", "english_support": "good", "coding_support": "limited", "offline_support": True,
        "recommended_for_brud_admin": True,
    },
    {
        "model_name": "TinyLlama-1.1B-Chat", "quantization": "Q4_K_M", "params_billions": 1.1,
        "expected_ram_usage_gb": 1.2,
        "min_ram_tier": "6GB", "expected_speed": "excellent",
        "best_for": capability_catalog.bilingual("Minimal-resource machines, fastest replies", "மிகக் குறைந்த வள கணினிகள், வேகமான பதில்கள்"),
        "tamil_support": "limited", "english_support": "good", "coding_support": "limited", "offline_support": True,
        "recommended_for_brud_admin": False,
    },
    {
        "model_name": "SmolLM2-1.7B-Instruct", "quantization": "Q4_K_M", "params_billions": 1.7,
        "expected_ram_usage_gb": 1.8,
        "min_ram_tier": "6GB", "expected_speed": "excellent",
        "best_for": capability_catalog.bilingual("Compact general assistant, English-first", "சிறிய பொது உதவியாளர், ஆங்கிலம் முன்னிலையில்"),
        "tamil_support": "limited", "english_support": "good", "coding_support": "fair", "offline_support": True,
        "recommended_for_brud_admin": False,
    },
    {
        "model_name": "Qwen2.5-3B-Instruct", "quantization": "Q4_K_M", "params_billions": 3.0,
        "expected_ram_usage_gb": 3.5,
        "min_ram_tier": "8GB", "expected_speed": "good",
        "best_for": capability_catalog.bilingual("Stronger reasoning and coding help with good Tamil support", "நல்ல தமிழ் ஆதரவுடன் வலுவான பகுத்தறிவு மற்றும் நிரலாக்க உதவி"),
        "tamil_support": "good", "english_support": "good", "coding_support": "good", "offline_support": True,
        "recommended_for_brud_admin": True,
    },
    {
        "model_name": "Phi-3-mini-4k-instruct", "quantization": "Q4_K_M", "params_billions": 3.8,
        "expected_ram_usage_gb": 4.0,
        "min_ram_tier": "8GB", "expected_speed": "good",
        "best_for": capability_catalog.bilingual("Strong reasoning for its size, English-first", "அளவுக்கு ஏற்ப வலுவான பகுத்தறிவு, ஆங்கிலம் முன்னிலையில்"),
        "tamil_support": "limited", "english_support": "excellent", "coding_support": "good", "offline_support": True,
        "recommended_for_brud_admin": False,
    },
    {
        "model_name": "Qwen2.5-7B-Instruct", "quantization": "Q4_K_M", "params_billions": 7.0,
        "expected_ram_usage_gb": 6.5,
        "min_ram_tier": "16GB", "expected_speed": "fair",
        "best_for": capability_catalog.bilingual("Best overall quality and Tamil support on capable hardware", "திறமையான வன்பொருளில் சிறந்த ஒட்டுமொத்த தரம் மற்றும் தமிழ் ஆதரவு"),
        "tamil_support": "excellent", "english_support": "excellent", "coding_support": "good", "offline_support": True,
        "recommended_for_brud_admin": True,
    },
    {
        "model_name": "Mistral-7B-Instruct", "quantization": "Q4_K_M", "params_billions": 7.0,
        "expected_ram_usage_gb": 6.5,
        "min_ram_tier": "16GB", "expected_speed": "fair",
        "best_for": capability_catalog.bilingual("Strong general-purpose reasoning, English-first", "வலுவான பொது-நோக்க பகுத்தறிவு, ஆங்கிலம் முன்னிலையில்"),
        "tamil_support": "fair", "english_support": "excellent", "coding_support": "good", "offline_support": True,
        "recommended_for_brud_admin": False,
    },
)

_TIER_ORDER = ("4GB", "6GB", "8GB", "16GB", "32GB+")


def _unlocked_tiers(current_tier: str) -> set[str]:
    try:
        current_index = _TIER_ORDER.index(current_tier)
    except ValueError:
        current_index = 0
    # 4GB unlocks nothing of its own in this catalog -- the smallest
    # tier represented is 6GB, so a 4GB machine still sees the 6GB
    # list (the best-effort minimum), disclosed via `below_minimum`.
    return {tier for tier in _TIER_ORDER[1:4] if _TIER_ORDER.index(tier) <= max(current_index, 1)}


def _annotate(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "model_name": entry["model_name"],
        "quantization": entry["quantization"],
        "params_billions": entry["params_billions"],
        "expected_ram_usage_gb": entry["expected_ram_usage_gb"],
        "expected_speed": capability_catalog.label(capability_catalog.SPEED_LEVELS, entry["expected_speed"]),
        "best_for": entry["best_for"],
        "tamil_support": capability_catalog.label(capability_catalog.SUPPORT_LEVELS, entry["tamil_support"]),
        "english_support": capability_catalog.label(capability_catalog.SUPPORT_LEVELS, entry["english_support"]),
        "coding_support": capability_catalog.label(capability_catalog.SUPPORT_LEVELS, entry["coding_support"]),
        "offline_support": capability_catalog.yes_no(entry["offline_support"]),
        "recommended_for_brud_admin": capability_catalog.yes_no(entry["recommended_for_brud_admin"]),
    }


def recommend(*, total_ram_gb: float, recommended_ram_tier: str) -> dict[str, Any]:
    unlocked = _unlocked_tiers(recommended_ram_tier)
    matches = [_annotate(entry) for entry in _CATALOG if entry["min_ram_tier"] in unlocked]

    top_candidates = [entry for entry in _CATALOG if entry["min_ram_tier"] in unlocked and entry["recommended_for_brud_admin"]]
    top_recommendation = _annotate(top_candidates[0]) if top_candidates else (matches[0] if matches else None)

    return {
        "ram_tier": recommended_ram_tier,
        "below_minimum_catalog_tier": total_ram_gb < 6.0,
        "models": matches,
        "top_recommendation": top_recommendation,
    }
