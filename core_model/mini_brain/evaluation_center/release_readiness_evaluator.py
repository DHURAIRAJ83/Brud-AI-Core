"""MB-19: Release Readiness Evaluator -- pure. Produces exactly one of
three categories -- Ready, Needs Review, Blocked -- from already-
computed benchmark composite scores. Every threshold used is a fixed,
documented constant below, never a hidden or learned value.
"""

from __future__ import annotations

from typing import Any

GROUNDING_QUALITY_THRESHOLD = 60.0
OCR_CONFLICT_THRESHOLD = 0.3
SEVERE_DRIFT_THRESHOLD = 0.15
READY_OVERALL_SCORE_THRESHOLD = 75.0
NEEDS_REVIEW_OVERALL_SCORE_THRESHOLD = 40.0

READY = "Ready"
NEEDS_REVIEW = "Needs Review"
BLOCKED = "Blocked"


def evaluate_release_readiness(
    *, overall_score: float | None, grounding_composite_score: float | None, package_integrity_ok: bool,
    ocr_conflict_ratio: float | None, drift_score: float | None,
) -> dict[str, Any]:
    blocking_issues: list[str] = []

    if grounding_composite_score is not None and grounding_composite_score < GROUNDING_QUALITY_THRESHOLD:
        blocking_issues.append(
            f"grounding quality {grounding_composite_score} is below the {GROUNDING_QUALITY_THRESHOLD} threshold"
        )
    if not package_integrity_ok:
        blocking_issues.append("package integrity check failed -- a checksum mismatch or missing file was detected")
    if ocr_conflict_ratio is not None and ocr_conflict_ratio > OCR_CONFLICT_THRESHOLD:
        blocking_issues.append(
            f"OCR conflict rate {ocr_conflict_ratio} exceeds the {OCR_CONFLICT_THRESHOLD} threshold"
        )
    if drift_score is not None and drift_score > SEVERE_DRIFT_THRESHOLD:
        blocking_issues.append(
            f"regression drift score {drift_score} exceeds the severe-drift threshold of {SEVERE_DRIFT_THRESHOLD}"
        )

    if blocking_issues:
        status = BLOCKED
    elif overall_score is not None and overall_score >= READY_OVERALL_SCORE_THRESHOLD:
        status = READY
    elif overall_score is not None and overall_score >= NEEDS_REVIEW_OVERALL_SCORE_THRESHOLD:
        status = NEEDS_REVIEW
    else:
        status = BLOCKED
        if overall_score is None:
            blocking_issues.append("no overall score could be computed -- insufficient benchmark coverage")
        else:
            blocking_issues.append(f"overall score {overall_score} is below the {NEEDS_REVIEW_OVERALL_SCORE_THRESHOLD} minimum")

    return {
        "status": status,
        "blocking_issues": blocking_issues,
        "thresholds": {
            "grounding_quality_threshold": GROUNDING_QUALITY_THRESHOLD,
            "ocr_conflict_threshold": OCR_CONFLICT_THRESHOLD,
            "severe_drift_threshold": SEVERE_DRIFT_THRESHOLD,
            "ready_overall_score_threshold": READY_OVERALL_SCORE_THRESHOLD,
            "needs_review_overall_score_threshold": NEEDS_REVIEW_OVERALL_SCORE_THRESHOLD,
        },
        "disclosure": (
            "release readiness is entirely metadata-based -- no model inference, no benchmark against "
            "real model outputs, and no semantic correctness verification was ever performed; every "
            "threshold above is a fixed heuristic, never calibrated against a real production outcome; "
            "this status never guarantees production model quality"
        ),
    }
