"""Licence governance.

Never assumes a licence family is approved without an explicit policy
mapping, and never infers public-domain status from source age alone
-- both must be an explicit, reviewed assertion. Website accessibility
never implies training permission by itself; only
``ai_training_permitted=True`` plus an ``approved``/
``approved_with_conditions`` review status together do.
"""

from __future__ import annotations

from typing import Any

from core_model.corpus import (
    BLOCKING_LICENCE_STATUSES,
    DEFAULT_APPROVED_LICENCE_FAMILIES,
    DEFAULT_CONDITIONAL_LICENCE_FAMILIES,
    LICENCE_FAMILIES,
    LICENCE_REVIEW_STATUSES,
)


def default_review_status_for_family(licence_family: str) -> str:
    """A starting suggestion only -- a human reviewer always makes the
    final ``review_status`` call; this never auto-approves anything."""

    if licence_family in DEFAULT_APPROVED_LICENCE_FAMILIES:
        return "approved"
    if licence_family in DEFAULT_CONDITIONAL_LICENCE_FAMILIES:
        return "approved_with_conditions"
    return "unknown"


def validate_licence_record(
    *, licence_family: str, review_status: str
) -> tuple[bool, str | None]:
    if licence_family not in LICENCE_FAMILIES:
        return False, "unsupported_licence_family"
    if review_status not in LICENCE_REVIEW_STATUSES:
        return False, "unsupported_review_status"
    return True, None


def assess_training_export_eligibility(
    *,
    review_status: str,
    ai_training_permitted: bool,
    source_status: str,
    intended_use: str,
    licence_family: str,
    expires_at_is_past: bool,
) -> dict[str, Any]:
    """Training export requires: AI-training permission granted,
    licence review approved/approved_with_conditions, source approved,
    and no expiry/dispute. Returns a decision plus the specific
    blocking reasons found -- never a bare boolean."""

    reasons: list[str] = []

    if expires_at_is_past:
        reasons.append("licence_expired")
    if review_status in BLOCKING_LICENCE_STATUSES:
        reasons.append(f"licence_review_status_{review_status}")
    if review_status not in {"approved", "approved_with_conditions"}:
        reasons.append("licence_not_approved")
    if not ai_training_permitted:
        reasons.append("ai_training_permission_absent")
    if source_status not in {"approved", "approved_with_restrictions"}:
        reasons.append(f"source_status_{source_status}_not_eligible")
    if licence_family == "research_only" and intended_use != "research":
        reasons.append("research_only_purpose_mismatch")
    if licence_family == "non_commercial" and intended_use == "commercial":
        reasons.append("non_commercial_purpose_conflict")

    eligible = not reasons
    return {"eligible": eligible, "blocking_reasons": reasons}
