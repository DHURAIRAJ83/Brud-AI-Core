"""Generic deterministic scoring helpers shared across evaluators.

Every score here is bounded and finite. ``None`` means "not evaluated"
(e.g. an empty sample group), never a fabricated zero.
"""

from __future__ import annotations

from core_model.model_evaluation import FAIL, NOT_EVALUATED, PASS, WARNING


def safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def classify_min_threshold(
    value: float | None, *, min_threshold: float, warn_margin: float = 0.0
) -> str:
    """pass if value >= min_threshold; warning within warn_margin below it; else fail."""

    if value is None:
        return NOT_EVALUATED
    if value >= min_threshold:
        return PASS
    if value >= min_threshold - warn_margin:
        return WARNING
    return FAIL


def classify_max_threshold(
    value: float | None, *, max_threshold: float, warn_margin: float = 0.0
) -> str:
    """pass if value <= max_threshold; warning within warn_margin above it; else fail."""

    if value is None:
        return NOT_EVALUATED
    if value <= max_threshold:
        return PASS
    if value <= max_threshold + warn_margin:
        return WARNING
    return FAIL


def average(values: list[float]) -> float | None:
    finite = [value for value in values if value is not None]
    if not finite:
        return None
    return sum(finite) / len(finite)


def bounded_score_0_1(passed: int, warned: int, failed: int) -> float | None:
    """A simple, transparent bounded score: pass=1.0, warning=0.5, fail=0.0, averaged."""

    total = passed + warned + failed
    if total == 0:
        return None
    return (passed * 1.0 + warned * 0.5 + failed * 0.0) / total
