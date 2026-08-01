"""Usage-eligibility policy for manual data records (Phase 3, Step 16).

Rule 15 requires usage decisions to call the Phase 2 policy engine
rather than duplicate rights logic -- this module never re-implements
`evaluate_source_usage`; it calls it, then layers three additional
gates that are specific to a *manually authored, reviewed* record
(lifecycle status, AI-assisted-without-review, high-risk-without-
verification) on top of whatever that call returns. If either layer
blocks the use, the combined decision is blocked.
"""

from __future__ import annotations

from typing import Any, TypedDict

from core_model.data_governance.usage_policy import evaluate_source_usage
from core_model.manual_data import (
    AI_ORIGIN_CREATION_METHODS,
    HIGH_FACT_DEPENDENCY,
    HIGH_RISK_KNOWLEDGE,
    TARGET_USES,
)

_STRONG_VERIFICATION_STATUSES = frozenset({"verified"})


class ManualUsageDecision(TypedDict):
    allowed: bool
    decision_code: str
    blocking_reasons: list[str]
    warnings: list[str]
    required_actions: list[str]


def _decision(
    allowed, code, reasons=None, warnings=None, *, required_actions=None
) -> ManualUsageDecision:
    return {
        "allowed": allowed,
        "decision_code": code,
        "blocking_reasons": reasons or [],
        "warnings": warnings or [],
        "required_actions": required_actions or [],
    }


def evaluate_manual_record_usage(
    *,
    record: dict[str, Any],
    source: dict[str, Any],
    rights: dict[str, Any] | None,
    verifications: list[dict[str, Any]] | None,
    target_use: str,
) -> ManualUsageDecision:
    if target_use not in TARGET_USES:
        raise ValueError(f"unsupported target_use: {target_use}")

    verifications = verifications or []
    status = record.get("status", "draft")

    if status == "rejected":
        return _decision(False, "BLOCKED_RECORD_REJECTED", ["record_status_rejected"])
    if status == "archived":
        return _decision(False, "BLOCKED_RECORD_REJECTED", ["record_status_archived"])
    if status != "approved" and target_use != "rag":
        return _decision(
            False,
            "BLOCKED_RECORD_NOT_APPROVED",
            ["record_not_yet_approved"],
            required_actions=["Complete review and approval before requesting this use."],
        )

    creation_method = record.get("creation_method", "admin_created")
    if creation_method in AI_ORIGIN_CREATION_METHODS and status != "approved":
        return _decision(
            False,
            "BLOCKED_AI_ASSISTED_UNREVIEWED",
            ["ai_assisted_content_requires_human_review"],
            required_actions=["Have a human reviewer approve this AI-assisted record."],
        )

    fact_dependency = record.get("fact_dependency", "none")
    knowledge_risk = record.get("knowledge_risk", "language_only")
    is_high_risk = knowledge_risk in HIGH_RISK_KNOWLEDGE or fact_dependency in HIGH_FACT_DEPENDENCY
    strong_verifications = [
        v for v in verifications if v.get("verification_status") in _STRONG_VERIFICATION_STATUSES
    ]
    if is_high_risk and not strong_verifications and target_use != "rag":
        return _decision(
            False,
            "BLOCKED_HIGH_RISK_UNVERIFIED",
            ["high_risk_or_fact_dependent_content_requires_verification"],
            required_actions=["Attach a supporting source and complete verification."],
        )

    source_decision = evaluate_source_usage(source=source, rights=rights, target_use=target_use)
    if not source_decision["allowed"]:
        return _decision(
            False,
            source_decision["decision_code"],
            source_decision["blocking_reasons"],
            source_decision["warnings"],
            required_actions=source_decision["required_actions"],
        )

    return _decision(
        True,
        "ALLOWED",
        [],
        source_decision["warnings"],
        required_actions=source_decision["required_actions"],
    )
