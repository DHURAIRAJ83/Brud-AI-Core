"""Reviewer-disagreement measurement and dataset-candidate quality
scoring.

Disagreement is measured explicitly and never silently averaged away:
a material split between reviewers must surface as
``requires_adjudication``, not get smoothed into a single mean score.
"""

from __future__ import annotations

import statistics
from typing import Any

from core_model.feedback import QUALITY_DIMENSIONS

_SCORE_FIELDS = (
    "correctness_score",
    "relevance_score",
    "language_quality_score",
    "safety_score",
    "citation_score",
    "retrieval_score",
    "memory_use_score",
    "overall_score",
)

MINOR_VARIANCE_THRESHOLD = 1.0
MATERIAL_VARIANCE_THRESHOLD = 2.0


def assess_review_disagreement(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    """``reviews`` is the list of append-only ``feedback_human_reviews``
    rows for one feedback event, most-recent-last. A single review can
    never disagree with itself -- returns ``none`` for 0 or 1 reviews."""

    if len(reviews) < 2:
        return {
            "status": "none",
            "classification_disagreement": False,
            "verdict_disagreement": False,
            "max_score_variance": 0.0,
        }

    classifications = {review.get("classification_confirmed") for review in reviews}
    classifications.discard(None)
    classification_disagreement = len(classifications) > 1

    verdicts = {review["verdict"] for review in reviews}
    verdict_disagreement = len(verdicts) > 1

    max_variance = 0.0
    for field in _SCORE_FIELDS:
        values = [review[field] for review in reviews if review.get(field) is not None]
        if len(values) >= 2:
            spread = max(values) - min(values)
            max_variance = max(max_variance, spread)

    correction_recommendations = {
        review["verdict"] in {"candidate_recommended", "regression_recommended"}
        for review in reviews
    }
    correction_disagreement = len(correction_recommendations) > 1

    if (
        classification_disagreement
        and verdict_disagreement
        and max_variance >= MATERIAL_VARIANCE_THRESHOLD
    ):
        status = "requires_adjudication"
    elif verdict_disagreement or max_variance >= MATERIAL_VARIANCE_THRESHOLD:
        status = "material"
    elif classification_disagreement or correction_disagreement or (
        max_variance >= MINOR_VARIANCE_THRESHOLD
    ):
        status = "minor"
    else:
        status = "none"

    return {
        "status": status,
        "classification_disagreement": classification_disagreement,
        "verdict_disagreement": verdict_disagreement,
        "correction_disagreement": correction_disagreement,
        "max_score_variance": max_variance,
    }


def median_score(reviews: list[dict[str, Any]], field: str = "overall_score") -> float | None:
    values = [review[field] for review in reviews if review.get(field) is not None]
    if not values:
        return None
    return statistics.median(values)


def assess_candidate_quality(
    *,
    privacy_status: str,
    safety_status: str,
    licence_status: str,
    deduplication_status: str,
    contamination_status: str,
    has_reviewer_evidence: bool,
    has_source_provenance: bool,
    correction_validation_status: str,
    detected_language: str,
    expected_language: str | None,
) -> dict[str, str]:
    """Deterministic pass/warning/fail/not_assessed status per quality
    dimension -- never a single opaque composite score."""

    result: dict[str, str] = dict.fromkeys(QUALITY_DIMENSIONS, "not_assessed")

    result["privacy_safety"] = (
        "fail" if privacy_status == "blocked" else "warning" if privacy_status != "safe" else "pass"
    )
    result["safety_quality"] = (
        "fail" if safety_status == "blocked" else "warning" if safety_status != "safe" else "pass"
    )
    result["licence_completeness"] = (
        "fail"
        if licence_status in {"unknown", "blocked"}
        else "warning"
        if licence_status == "restricted"
        else "pass"
    )
    result["deduplication"] = "pass" if deduplication_status == "unique" else "fail"
    result["contamination_safety"] = "pass" if contamination_status == "clean" else "fail"
    result["provenance_completeness"] = "pass" if has_source_provenance else "fail"
    result["correctness_support"] = "pass" if has_reviewer_evidence else "warning"
    result["instruction_quality"] = (
        "pass" if correction_validation_status == "validated" else "warning"
        if correction_validation_status == "validated_with_warnings"
        else "fail"
    )
    result["response_quality"] = result["instruction_quality"]
    result["clarity"] = "pass" if correction_validation_status != "rejected" else "fail"
    result["format_quality"] = "pass" if correction_validation_status != "rejected" else "fail"
    if expected_language and expected_language not in {"unknown", "auto"}:
        result["language_quality"] = (
            "pass" if detected_language in {expected_language, "mixed"} else "fail"
        )
    else:
        result["language_quality"] = "pass"
    result["citation_quality"] = "not_assessed"

    return result


def overall_candidate_verdict(dimension_results: dict[str, str]) -> str:
    """``fail`` on any blocking dimension outranks a mere ``warning``."""

    if any(status == "fail" for status in dimension_results.values()):
        return "fail"
    if any(status == "warning" for status in dimension_results.values()):
        return "warning"
    return "pass"
