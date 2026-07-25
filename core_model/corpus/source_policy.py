"""Corpus policy and source-registry validation.

A corpus policy must fail closed: every default requirement flag
starts ``true``, and a source may only be considered training-eligible
once every applicable requirement is satisfied.
"""

from __future__ import annotations

from typing import Any

from core_model.corpus import SOURCE_STATUSES, SOURCE_TYPES


def validate_policy_bounds(
    *,
    maximum_source_bytes: int,
    maximum_document_characters: int,
    maximum_segment_characters: int,
    minimum_segment_characters: int,
) -> tuple[bool, str | None]:
    if maximum_source_bytes <= 0:
        return False, "maximum_source_bytes must be positive"
    if maximum_document_characters <= 0:
        return False, "maximum_document_characters must be positive"
    if minimum_segment_characters <= 0:
        return False, "minimum_segment_characters must be positive"
    if maximum_segment_characters <= minimum_segment_characters:
        return False, "maximum_segment_characters must exceed minimum_segment_characters"
    return True, None


def validate_source_type(
    source_type: str, allowed_source_types: list[str]
) -> tuple[bool, str | None]:
    if source_type not in SOURCE_TYPES:
        return False, "unsupported_source_type"
    if allowed_source_types and source_type not in allowed_source_types:
        return False, "source_type_not_allowed_by_policy"
    return True, None


def source_is_training_eligible(
    *,
    status: str,
    require_verified_origin: bool,
    origin_verified: bool,
) -> tuple[bool, str | None]:
    """A source may enter a normal build only once ``approved``
    (or ``approved_with_restrictions`` for a build whose exact purpose
    matches the restriction). Anything else -- draft, under review,
    rejected, quarantined, disputed, archived -- is never eligible."""

    if status not in SOURCE_STATUSES:
        return False, "unsupported_status"
    if require_verified_origin and not origin_verified:
        return False, "origin_not_verified"
    if status == "approved":
        return True, None
    if status == "approved_with_restrictions":
        return True, "restricted_purpose_match_required"
    return False, f"source_status_{status}_not_eligible"


def summarize_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Bounded, non-secret summary suitable for API/manifest exposure."""

    return {
        "name": policy.get("name"),
        "lifecycle_status": policy.get("lifecycle_status"),
        "require_verified_origin": bool(policy.get("require_verified_origin")),
        "require_licence_review": bool(policy.get("require_licence_review")),
        "require_privacy_scan": bool(policy.get("require_privacy_scan")),
        "require_safety_scan": bool(policy.get("require_safety_scan")),
        "require_quality_assessment": bool(policy.get("require_quality_assessment")),
        "require_deduplication": bool(policy.get("require_deduplication")),
        "require_contamination_check": bool(policy.get("require_contamination_check")),
    }
