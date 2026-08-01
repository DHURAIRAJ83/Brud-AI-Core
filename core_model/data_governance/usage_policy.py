"""Usage-eligibility policy for the Source, Rights & Usage Registry.

Pure functions only -- no database access, no filesystem access, no
imports of backend/frontend code. Every decision is deterministic given
its inputs and returns the specific blocking reasons found, never a
bare boolean (mirroring ``core_model.corpus.licence_policy``).

Deliberately never consults ``source_url``, hosting, publication age,
or the presence/absence of a copyright notice -- rule 10 of the Phase 2
task is enforced structurally here by simply never reading those
fields, rather than by a comment promising not to.
"""

from __future__ import annotations

from typing import Any, TypedDict

from core_model.data_governance import (
    AI_ORIGIN_SOURCE_TYPES,
    STRONG_VERIFICATION_STATUSES,
    TARGET_USES,
)


class UsageDecision(TypedDict):
    allowed: bool
    decision_code: str
    blocking_reasons: list[str]
    warnings: list[str]
    required_actions: list[str]


def _decision(
    allowed: bool,
    code: str,
    blocking_reasons: list[str] | None = None,
    warnings: list[str] | None = None,
    required_actions: list[str] | None = None,
) -> UsageDecision:
    return {
        "allowed": allowed,
        "decision_code": code,
        "blocking_reasons": blocking_reasons or [],
        "warnings": warnings or [],
        "required_actions": required_actions or [],
    }


_TARGET_USE_FLAGS: dict[str, tuple[str, str]] = {
    "rag": ("rag_use_allowed", "BLOCKED_RAG_NOT_ALLOWED"),
    "training": ("training_use_allowed", "BLOCKED_TRAINING_NOT_ALLOWED"),
    "evaluation": ("evaluation_use_allowed", "BLOCKED_EVALUATION_NOT_ALLOWED"),
    "commercial": ("commercial_use_allowed", "BLOCKED_COMMERCIAL_NOT_ALLOWED"),
    "public_export": ("public_export_allowed", "BLOCKED_PUBLIC_EXPORT_NOT_ALLOWED"),
    "redistribution": ("redistribution_allowed", "BLOCKED_REDISTRIBUTION_NOT_ALLOWED"),
}

_EXTERNAL_USES = frozenset({"public_export", "commercial", "redistribution"})


def evaluate_source_usage(
    *,
    source: dict[str, Any],
    rights: dict[str, Any] | None,
    target_use: str,
) -> UsageDecision:
    """Decide whether ``source`` (with its current ``rights``, if any) may
    be used for ``target_use``.

    ``source`` is expected to carry at least ``status`` and
    ``source_type``, and may carry ``independent_reviewer_required`` and
    ``internal_rag_policy_allows_unknown_rights`` (an explicit,
    admin-configured policy flag -- rule 9 requires this to be explicit,
    never assumed). ``rights`` is expected to carry the shape of a
    ``source_rights`` row (or an adapted ``corpus_source_licences`` row,
    see ``rights_from_corpus_licence_row``); ``None`` means no rights
    declaration exists yet at all.
    """

    if target_use not in TARGET_USES:
        raise ValueError(f"unsupported target_use: {target_use}")

    source_status = source.get("status", "draft")
    if source_status == "rejected":
        return _decision(
            False,
            "BLOCKED_SOURCE_REJECTED",
            ["source_status_rejected"],
            required_actions=["A rejected source cannot be used for anything."],
        )
    if source_status == "archived":
        return _decision(
            False,
            "BLOCKED_SOURCE_REJECTED",
            ["source_status_archived"],
            required_actions=["Restore the source from the archive before requesting use."],
        )
    if source_status == "restricted" and target_use != "rag":
        return _decision(
            False,
            "BLOCKED_SOURCE_REJECTED",
            ["source_status_restricted"],
            required_actions=["A restricted source only remains eligible for internal RAG."],
        )

    rights_status = (rights or {}).get("rights_status", "unknown")

    if rights_status == "prohibited":
        return _decision(False, "BLOCKED_SOURCE_REJECTED", ["rights_status_prohibited"])

    if rights_status == "expired" or (rights or {}).get("permission_expired"):
        return _decision(
            False,
            "BLOCKED_LICENSE_EXPIRED",
            ["permission_or_license_expired"],
            required_actions=["Renew or replace the expired permission/licence."],
        )

    if rights is None or rights_status in ("unknown", "pending_review"):
        if target_use == "rag" and source.get("internal_rag_policy_allows_unknown_rights"):
            return _decision(
                True,
                "REVIEW_REQUIRED_INTERNAL_RAG",
                [],
                warnings=["rights_not_yet_confirmed"],
                required_actions=[
                    "Complete rights review before this leaves internal/private RAG use."
                ],
            )
        if rights_status == "pending_review":
            return _decision(
                False,
                "BLOCKED_PERMISSION_PENDING",
                ["rights_pending_review"],
                required_actions=["Wait for the rights review to complete."],
            )
        return _decision(
            False,
            "BLOCKED_RIGHTS_UNKNOWN",
            ["rights_unknown"],
            required_actions=["Declare and submit source rights information for review."],
        )

    # From here, rights is a real declaration with concrete flags.
    verification_status = rights.get("verification_status", "unverified")
    source_type = source.get("source_type", "unknown")

    if (
        source_type in AI_ORIGIN_SOURCE_TYPES
        and verification_status not in STRONG_VERIFICATION_STATUSES
        and target_use != "rag"
    ):
        return _decision(
            False,
            "BLOCKED_VERIFICATION_REQUIRED",
            ["ai_origin_content_requires_human_review"],
            required_actions=["Have a human reviewer verify this AI-assisted/generated content."],
        )

    if (
        source.get("independent_reviewer_required")
        and verification_status not in STRONG_VERIFICATION_STATUSES
        and target_use in ("training", "commercial", "public_export")
    ):
        return _decision(
            False,
            "BLOCKED_VERIFICATION_REQUIRED",
            ["independent_review_required"],
            required_actions=[
                "Obtain independent or legal verification for this high-risk content."
            ],
        )

    flag_name, blocked_code = _TARGET_USE_FLAGS[target_use]
    if not rights.get(flag_name):
        return _decision(
            False,
            blocked_code,
            [f"{flag_name}_is_false"],
            required_actions=[f"Update rights to explicitly allow {target_use} use."],
        )

    if rights.get("internal_only") and target_use in _EXTERNAL_USES:
        return _decision(
            False,
            blocked_code,
            ["internal_only_restricts_external_use"],
            required_actions=["Rights are marked internal-only; this cannot leave Brud AI."],
        )

    warnings: list[str] = []
    required_actions: list[str] = []

    if (
        target_use == "public_export"
        and rights.get("attribution_required")
        and not rights.get("attribution_text")
    ):
        warnings.append("attribution_required_but_no_attribution_text_set")
        required_actions.append("Provide attribution text before exporting.")

    if target_use == "commercial" and verification_status not in STRONG_VERIFICATION_STATUSES:
        warnings.append("commercial_use_without_strong_verification")

    return _decision(True, "ALLOWED", [], warnings, required_actions)


def validate_rights_combination(rights: dict[str, Any]) -> list[str]:
    """Structural validation for a rights declaration, independent of any
    particular target use (Step 13). Returns user-friendly error strings;
    empty list means the combination is internally consistent."""

    errors: list[str] = []
    rights_status = rights.get("rights_status", "unknown")

    if rights_status == "open_license" and not (
        rights.get("license_identifier") or rights.get("license_name")
    ):
        errors.append("An open_license rights status requires a license name or identifier.")

    if rights_status == "permission_granted" and not rights.get("permission_reference"):
        errors.append("A permission_granted rights status requires a permission reference.")

    if rights.get("public_export_allowed") and not rights.get("redistribution_allowed"):
        errors.append("public_export_allowed cannot be true while redistribution_allowed is false.")

    verification_status = rights.get("verification_status", "unverified")
    if (
        rights.get("commercial_use_allowed")
        and verification_status not in STRONG_VERIFICATION_STATUSES
    ):
        errors.append(
            "commercial_use_allowed requires verified rights "
            "(document_verified, owner_confirmed, or legal_reviewed)."
        )

    if rights.get("training_use_allowed") and rights_status in ("unknown", "pending_review"):
        errors.append(
            "training_use_allowed must not be true while rights are unknown or pending review."
        )

    if rights.get("public_export_allowed") and rights_status in ("unknown", "pending_review"):
        errors.append(
            "public_export_allowed must not be true while rights are unknown or pending review."
        )

    return errors


def rights_from_corpus_licence_row(row: dict[str, Any]) -> dict[str, Any]:
    """Adapt an existing ``corpus_source_licences`` row into the same
    normalized shape ``evaluate_source_usage`` expects, so the corpus
    pipeline's already-governed licences can be evaluated by the same
    policy brain without duplicating it or altering their table."""

    review_status = row.get("review_status", "unknown")
    blocked_review_statuses = {"blocked", "disputed", "expired", "restricted"}
    if review_status in blocked_review_statuses:
        rights_status = "restricted" if review_status == "restricted" else review_status
        if review_status == "expired":
            rights_status = "expired"
        elif review_status in ("blocked", "disputed"):
            rights_status = "prohibited" if review_status == "blocked" else "unknown"
    elif review_status in ("approved", "approved_with_conditions"):
        rights_status = "licensed"
    else:
        rights_status = "unknown"

    evidence_type = row.get("evidence_type", "admin_asserted")
    verification_status = {
        "admin_asserted": "self_declared",
        "document_evidence": "document_verified",
        "owner_confirmation": "owner_confirmed",
        "legal_review": "legal_reviewed",
    }.get(evidence_type, "self_declared")

    return {
        "rights_status": rights_status,
        "license_name": row.get("licence_name"),
        "verification_status": verification_status,
        "attribution_required": bool(row.get("attribution_required")),
        "attribution_text": row.get("copyright_holder"),
        "modification_allowed": bool(row.get("modification_permitted")),
        "commercial_use_allowed": bool(row.get("commercial_use_permitted")),
        "rag_use_allowed": bool(row.get("ai_training_permitted"))
        or review_status in ("approved", "approved_with_conditions"),
        "training_use_allowed": bool(row.get("ai_training_permitted")),
        "evaluation_use_allowed": bool(row.get("ai_training_permitted")),
        "public_export_allowed": bool(row.get("redistribution_permitted")),
        "redistribution_allowed": bool(row.get("redistribution_permitted")),
        "internal_only": False,
        "permission_expired": _is_past(row.get("expires_at")),
    }


def rights_from_source_rights_row(row: dict[str, Any]) -> dict[str, Any]:
    """Adapt a native ``source_rights`` row (already a dict via the
    repository's ``public_row``) into the shape ``evaluate_source_usage``
    expects. Present mainly so callers always go through one adapter
    entry point regardless of which table the rights came from."""

    return {
        **row,
        "permission_expired": _is_past(row.get("permission_expires_at")),
    }


def _is_past(value: str | None) -> bool:
    if not value:
        return False
    from datetime import UTC, datetime

    try:
        expires_at = datetime.fromisoformat(value)
    except ValueError:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return expires_at <= datetime.now(UTC)
