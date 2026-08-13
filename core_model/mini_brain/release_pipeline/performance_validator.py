"""MB-07: Performance Validation -- pure. Classifies real, already
-measured performance numbers against fixed, disclosed thresholds.
These thresholds are not empirically validated against production
traffic -- same honesty standard as MB-05's dataset-readiness
thresholds and MB-06's hyperparameter presets -- they exist to give an
admin a consistent frame of reference, not a guarantee.
"""

from __future__ import annotations

from typing import Any

# CPU-only, single small-model assumptions -- disclosed, not tuned.
LOAD_TIME_MS_FAST = 3_000
LOAD_TIME_MS_ACCEPTABLE = 15_000
MEMORY_BYTES_FAST = 2 * 1024**3
MEMORY_BYTES_ACCEPTABLE = 8 * 1024**3
TOKENS_PER_SECOND_FAST = 15.0
TOKENS_PER_SECOND_ACCEPTABLE = 4.0
LATENCY_MS_FAST = 500
LATENCY_MS_ACCEPTABLE = 3_000

_TIER_ORDER = {"Fast": 0, "Acceptable": 1, "Slow": 2}


def _tier(value: float, fast_bound: float, acceptable_bound: float, *, lower_is_better: bool) -> str:
    if lower_is_better:
        if value <= fast_bound:
            return "Fast"
        if value <= acceptable_bound:
            return "Acceptable"
        return "Slow"
    if value >= fast_bound:
        return "Fast"
    if value >= acceptable_bound:
        return "Acceptable"
    return "Slow"


def classify_performance(
    *,
    load_time_ms: float,
    memory_bytes: int,
    tokens_per_second: float,
    prompt_latency_ms: float,
    generation_latency_ms: float,
) -> dict[str, Any]:
    tiers = {
        "load_time": _tier(load_time_ms, LOAD_TIME_MS_FAST, LOAD_TIME_MS_ACCEPTABLE, lower_is_better=True),
        "memory": _tier(memory_bytes, MEMORY_BYTES_FAST, MEMORY_BYTES_ACCEPTABLE, lower_is_better=True),
        "tokens_per_second": _tier(tokens_per_second, TOKENS_PER_SECOND_FAST, TOKENS_PER_SECOND_ACCEPTABLE, lower_is_better=False),
        "prompt_latency": _tier(prompt_latency_ms, LATENCY_MS_FAST, LATENCY_MS_ACCEPTABLE, lower_is_better=True),
        "generation_latency": _tier(generation_latency_ms, LATENCY_MS_FAST, LATENCY_MS_ACCEPTABLE, lower_is_better=True),
    }
    overall_tier = max(tiers.values(), key=lambda tier: _TIER_ORDER[tier])
    return {
        "measurements": {
            "load_time_ms": load_time_ms, "memory_bytes": memory_bytes,
            "tokens_per_second": tokens_per_second, "prompt_latency_ms": prompt_latency_ms,
            "generation_latency_ms": generation_latency_ms,
        },
        "tiers": tiers,
        "overall_tier": overall_tier,
    }
