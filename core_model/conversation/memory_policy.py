"""Memory category, purpose, and consent-gate policy checks.

Sensitive categories are rejected structurally (they are simply not
members of ``MEMORY_CATEGORIES``); this module supplies the honest,
specific reasons an admin or service should surface when a proposal is
rejected, and the consent/confirmation gates that decide whether a
proposed memory item may ever reach ``active`` status.
"""

from __future__ import annotations

from core_model.conversation import (
    FORBIDDEN_MEMORY_CATEGORIES,
    MEMORY_CATEGORIES,
    MEMORY_PURPOSES,
)


def category_is_allowed(
    category: str, policy_allowed_categories: list[str]
) -> tuple[bool, str | None]:
    if category in FORBIDDEN_MEMORY_CATEGORIES:
        return False, "forbidden_sensitive_category"
    if category not in MEMORY_CATEGORIES:
        return False, "unsupported_category"
    if policy_allowed_categories and category not in policy_allowed_categories:
        return False, "category_not_allowed_by_policy"
    return True, None


def purpose_is_bounded(
    purpose: str, allowed_purposes: list[str] | None = None
) -> tuple[bool, str | None]:
    if purpose not in MEMORY_PURPOSES:
        return False, "unbounded_purpose"
    if allowed_purposes and purpose not in allowed_purposes:
        return False, "purpose_not_allowed_by_consent"
    return True, None


def consent_permits_category(consent: dict, category: str) -> tuple[bool, str | None]:
    if consent.get("status") != "active":
        return False, "consent_not_active"
    prohibited = consent.get("prohibited_categories", [])
    if category in prohibited:
        return False, "category_prohibited_by_consent"
    allowed = consent.get("allowed_categories", [])
    if allowed and category not in allowed:
        return False, "category_not_covered_by_consent"
    return True, None


def may_become_active(
    *,
    creation_source: str,
    confidence_type: str,
    consent: dict | None,
    category: str,
    safety_status: str,
    is_duplicate: bool,
    has_unconfirmed_conflict: bool,
) -> tuple[bool, str | None]:
    """Decides whether a proposed memory item may transition straight to
    ``active``. ``assistant_proposed``/``assistant_inferred`` memory can
    never become active without an explicit confirmation step."""

    if safety_status == "blocked":
        return False, "safety_blocked"
    if creation_source in {"assistant_proposed"} or confidence_type == "assistant_inferred":
        return False, "requires_confirmation"
    if creation_source == "system_derived" and confidence_type != "deterministically_extracted":
        return False, "requires_confirmation"
    if creation_source in {"explicit_user_request", "system_derived"} and consent is None:
        return False, "consent_required"
    if consent is not None:
        allowed, reason = consent_permits_category(consent, category)
        if not allowed:
            return False, reason
    if is_duplicate:
        return False, "duplicate"
    if has_unconfirmed_conflict:
        return False, "conflict_requires_confirmation"
    return True, None
