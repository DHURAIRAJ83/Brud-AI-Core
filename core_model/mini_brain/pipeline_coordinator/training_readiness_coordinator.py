"""MB-12: Training Readiness Coordinator -- pure. Combines
already-fetched readiness/quality signals from MB-05, MB-05.1, MB-06,
MB-08, MB-09, MB-10, and MB-11 into one unified 0-100 readiness score
with a per-source breakdown. Any source not yet available (nothing
linked yet) is simply omitted from the average, never treated as zero.
"""

from __future__ import annotations

from typing import Any

_STATUS_SCORE = {"Ready": 100.0, "Needs Improvement": 55.0, "Not Ready": 15.0}


def coordinate_training_readiness(
    *,
    mb05_training_status: str | None,
    mb051_overall_score: float | None,
    mb06_quality_score: float | None,
    mb08_average_failure_rate: float | None,
    mb09_recurring_weak_domain_count: int | None,
    mb10_quality_score: float | None,
    mb11_predicted_quality_score: float | None,
) -> dict[str, Any]:
    sources: dict[str, float] = {}
    if mb05_training_status is not None:
        sources["mb05_dataset_intelligence"] = _STATUS_SCORE.get(mb05_training_status, 50.0)
    if mb051_overall_score is not None:
        sources["mb051_advanced_dataset_intelligence"] = mb051_overall_score
    if mb06_quality_score is not None:
        sources["mb06_learning_supervisor"] = mb06_quality_score
    if mb08_average_failure_rate is not None:
        sources["mb08_continuous_learning"] = round(max(0.0, 100.0 - mb08_average_failure_rate * 100), 1)
    if mb09_recurring_weak_domain_count is not None:
        sources["mb09_planning_center"] = round(max(0.0, 100.0 - mb09_recurring_weak_domain_count * 10.0), 1)
    if mb10_quality_score is not None:
        sources["mb10_research_center"] = mb10_quality_score
    if mb11_predicted_quality_score is not None:
        sources["mb11_dataset_evolution"] = mb11_predicted_quality_score

    unified_score = round(sum(sources.values()) / len(sources), 1) if sources else 0.0
    if unified_score >= 80.0:
        status = "Ready"
    elif unified_score >= 50.0:
        status = "Needs Improvement"
    else:
        status = "Not Ready"

    return {
        "per_source_scores": sources,
        "sources_available": len(sources),
        "sources_total": 7,
        "unified_readiness_score": unified_score,
        "status": status,
    }
