"""MB-21: Evaluation Scoring -- pure. Derives a disclosed confidence
label from already-computed agreement/failure/safety signals -- never
a claim of correctness, only of how much cross-provider signal exists
to review.
"""

from __future__ import annotations

from typing import Any

HIGH_CONFIDENCE_THRESHOLD = 70.0
MEDIUM_CONFIDENCE_THRESHOLD = 40.0


def score_evaluation(
    *, agreement_report: dict[str, Any], failure_report: dict[str, Any], safety_report: dict[str, Any],
) -> dict[str, Any]:
    if agreement_report["successful_provider_count"] == 0:
        confidence_level = "no_signal"
    elif safety_report["has_violations"]:
        confidence_level = "low"
    elif agreement_report["agreement_score"] >= HIGH_CONFIDENCE_THRESHOLD and agreement_report["successful_provider_count"] >= 2:
        confidence_level = "high"
    elif agreement_report["agreement_score"] >= MEDIUM_CONFIDENCE_THRESHOLD:
        confidence_level = "medium"
    else:
        confidence_level = "low"

    return {
        "confidence_level": confidence_level,
        "successful_provider_count": agreement_report["successful_provider_count"],
        "agreement_score": agreement_report["agreement_score"],
        "has_safety_flags": safety_report["has_violations"],
        "all_providers_failed": failure_report["all_providers_failed"],
        "thresholds": {
            "high_confidence_agreement_score": HIGH_CONFIDENCE_THRESHOLD,
            "medium_confidence_agreement_score": MEDIUM_CONFIDENCE_THRESHOLD,
        },
        "disclosure": (
            "confidence_level describes how much cross-provider lexical signal exists to review -- it "
            "is never a claim that the underlying content is correct; agreement does not imply "
            "correctness"
        ),
    }
