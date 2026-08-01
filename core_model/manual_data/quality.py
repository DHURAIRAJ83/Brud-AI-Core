"""Deterministic quality assessment for manual data records (Phase 3, Step 7).

Mirrors the shape of `backend.services.dataset_quality`: per-dimension
0-100 scores plus a set of severity-independent *blocking issue* codes
that force the recommended status regardless of how high the average
score is -- a record with one blocking issue is never recommended for
approval just because its other dimensions score well.
"""

from __future__ import annotations

from typing import Any, TypedDict

from core_model.manual_data import (
    AI_ORIGIN_CREATION_METHODS,
    HIGH_FACT_DEPENDENCY,
    HIGH_RISK_KNOWLEDGE,
)
from core_model.manual_data.validation import validate_record_fields

DIMENSIONS = (
    "language_correctness",
    "meaning_correctness",
    "naturalness",
    "completeness",
    "source_reliability",
    "factual_confidence",
    "format_validity",
    "uniqueness",
)

DEFAULT_APPROVAL_THRESHOLD = 85

_STRONG_VERIFICATION_STATUSES = frozenset({"verified"})


class QualityResult(TypedDict):
    dimension_scores: dict[str, float]
    overall_score: float
    blocking_issues: list[str]
    warnings: list[str]
    recommended_status: str


def assess_quality(
    *,
    record: dict[str, Any],
    fields: dict[str, Any],
    reviews: list[dict[str, Any]] | None = None,
    verifications: list[dict[str, Any]] | None = None,
    duplicate_status: str = "unique",
    usage_decision: dict[str, Any] | None = None,
    approval_threshold: int = DEFAULT_APPROVAL_THRESHOLD,
) -> QualityResult:
    reviews = reviews or []
    verifications = verifications or []

    record_type = record["record_type"]
    creation_method = record.get("creation_method", "admin_created")
    fact_dependency = record.get("fact_dependency", "none")
    knowledge_risk = record.get("knowledge_risk", "language_only")

    validation_errors = validate_record_fields(record_type, {**fields, **record})
    approved_reviews = [r for r in reviews if r.get("review_status") == "approved"]
    language_reviews = [r for r in approved_reviews if r.get("review_type") == "language"]
    translation_reviews = [r for r in approved_reviews if r.get("review_type") == "translation"]
    rejected_reviews = [r for r in reviews if r.get("review_status") == "rejected"]

    is_high_risk = knowledge_risk in HIGH_RISK_KNOWLEDGE or fact_dependency in HIGH_FACT_DEPENDENCY
    strong_verifications = [
        v for v in verifications if v.get("verification_status") in _STRONG_VERIFICATION_STATUSES
    ]
    rejected_verifications = [
        v for v in verifications if v.get("verification_status") == "rejected"
    ]

    blocking_issues: list[str] = []
    warnings: list[str] = []

    if not record.get("source_id") and not record.get("source_public_id"):
        blocking_issues.append("MISSING_SOURCE")
    if validation_errors:
        blocking_issues.append("EMPTY_REQUIRED_FIELD")
    if is_high_risk and not strong_verifications:
        blocking_issues.append("HIGH_RISK_UNVERIFIED")
    if creation_method in AI_ORIGIN_CREATION_METHODS and not approved_reviews:
        blocking_issues.append("AI_ASSISTED_UNREVIEWED")
    if record_type == "translation_pair":
        if fields.get("input_language") and fields.get("input_language") == fields.get(
            "output_language"
        ):
            blocking_issues.append("INVALID_LANGUAGE_PAIR")
        if not translation_reviews:
            blocking_issues.append("TRANSLATION_UNVERIFIED")
    if rejected_verifications or rejected_reviews:
        blocking_issues.append("FACTUAL_CONFLICT")
    if usage_decision is not None and not usage_decision.get("allowed"):
        blocking_issues.append("RIGHTS_BLOCK_TRAINING")

    dimension_scores: dict[str, float] = {
        "completeness": 100.0
        if not validation_errors
        else max(0.0, 100.0 - 25.0 * len(validation_errors)),
        "format_validity": 100.0 if not validation_errors else 0.0,
        "language_correctness": 100.0
        if language_reviews
        else (55.0 if record.get("primary_language") else 20.0),
        "meaning_correctness": (
            sum(r.get("meaning_score") or 70.0 for r in approved_reviews) / len(approved_reviews)
            if approved_reviews
            else 65.0
        ),
        "naturalness": (
            sum(r.get("naturalness_score") or 70.0 for r in approved_reviews)
            / len(approved_reviews)
            if approved_reviews
            else 65.0
        ),
        "source_reliability": 100.0 if strong_verifications else (50.0 if verifications else 40.0),
        "factual_confidence": (
            100.0 if not is_high_risk else (100.0 if strong_verifications else 15.0)
        ),
        "uniqueness": {"unique": 100.0, "possible_duplicate": 50.0}.get(duplicate_status, 0.0),
    }

    overall_score = round(sum(dimension_scores.values()) / len(dimension_scores), 2)

    if duplicate_status == "exact_duplicate":
        warnings.append("exact_duplicate_content_detected")
    elif duplicate_status == "possible_duplicate":
        warnings.append("possible_duplicate_content_detected")

    if blocking_issues:
        if "MISSING_SOURCE" in blocking_issues or "EMPTY_REQUIRED_FIELD" in blocking_issues:
            recommended_status = "draft"
        elif "HIGH_RISK_UNVERIFIED" in blocking_issues:
            recommended_status = "needs_source_verification"
        else:
            recommended_status = "needs_review"
    elif overall_score >= approval_threshold:
        recommended_status = "approved"
    else:
        recommended_status = "needs_review"

    return {
        "dimension_scores": dimension_scores,
        "overall_score": overall_score,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "recommended_status": recommended_status,
    }
