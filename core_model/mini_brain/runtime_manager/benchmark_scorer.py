"""MB-30: Benchmark Scorer -- pure. Given already-measured metrics
(the service layer runs the real timed prompt), returns a qualitative
Excellent/Good/Fair/Poor rating -- thresholds calibrated for CPU-only
inference on small (1-4B parameter) quantized models, not GPU-class
throughput.
"""

from __future__ import annotations

from typing import Any

_RATING_LABELS: dict[str, dict[str, str]] = {
    "excellent": {"en": "Excellent", "ta": "மிகச் சிறந்தது"},
    "good": {"en": "Good", "ta": "நல்லது"},
    "fair": {"en": "Fair", "ta": "மிதமானது"},
    "poor": {"en": "Poor", "ta": "மோசமானது"},
}

_EXCELLENT_TOKENS_PER_SECOND = 15.0
_GOOD_TOKENS_PER_SECOND = 8.0
_FAIR_TOKENS_PER_SECOND = 3.0


def _rate(tokens_per_second: float) -> str:
    if tokens_per_second >= _EXCELLENT_TOKENS_PER_SECOND:
        return "excellent"
    if tokens_per_second >= _GOOD_TOKENS_PER_SECOND:
        return "good"
    if tokens_per_second >= _FAIR_TOKENS_PER_SECOND:
        return "fair"
    return "poor"


def score(
    *, load_time_ms: float, first_token_latency_ms: float, tokens_per_second: float, peak_ram_mb: float,
) -> dict[str, Any]:
    rating = _rate(tokens_per_second)
    return {
        "rating": rating,
        "rating_label": _RATING_LABELS[rating],
        "load_time_ms": load_time_ms,
        "first_token_latency_ms": first_token_latency_ms,
        "tokens_per_second": tokens_per_second,
        "peak_ram_mb": peak_ram_mb,
    }
