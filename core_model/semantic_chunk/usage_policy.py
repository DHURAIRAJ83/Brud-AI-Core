"""Usage-eligibility policy for structured record candidates (Phase 5,
Step 22). Never re-implements Phase 2's `evaluate_source_usage` --
calls it directly, then layers gates specific to a *chunk-derived*
structured record (candidate status, human-synthesized content not yet
reviewed) on top of whatever that call returns.
"""

from __future__ import annotations

from typing import Any, TypedDict

from core_model.data_governance.usage_policy import TARGET_USES, evaluate_source_usage


class StructuredRecordUsageDecision(TypedDict):
    allowed: bool
    decision_code: str
    blocking_reasons: list[str]
    warnings: list[str]
    required_actions: list[str]


def _decision(
    allowed, code, reasons=None, warnings=None, *, required_actions=None
) -> StructuredRecordUsageDecision:
    return {
        "allowed": allowed,
        "decision_code": code,
        "blocking_reasons": reasons or [],
        "warnings": warnings or [],
        "required_actions": required_actions or [],
    }


def evaluate_structured_record_usage(
    *,
    candidate: dict[str, Any],
    source: dict[str, Any],
    rights: dict[str, Any] | None,
    target_use: str,
) -> StructuredRecordUsageDecision:
    if target_use not in TARGET_USES:
        raise ValueError(f"unsupported target_use: {target_use}")

    status = candidate.get("status", "draft")
    if status == "rejected":
        return _decision(False, "BLOCKED_CANDIDATE_REJECTED", ["candidate_status_rejected"])
    if status == "archived":
        return _decision(False, "BLOCKED_CANDIDATE_REJECTED", ["candidate_status_archived"])
    if status != "approved" and target_use != "rag":
        return _decision(
            False,
            "BLOCKED_CANDIDATE_NOT_APPROVED",
            ["candidate_not_yet_approved"],
            required_actions=["Complete review and approval before requesting this use."],
        )

    origin = candidate.get("origin", "source_grounded")
    if origin == "human_synthesized" and not candidate.get("reviewed") and target_use != "rag":
        return _decision(
            False,
            "BLOCKED_UNREVIEWED_SYNTHESIS",
            ["human_synthesized_content_requires_human_review"],
            required_actions=["Have a human reviewer confirm this synthesized content."],
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
