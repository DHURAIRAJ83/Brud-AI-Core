"""Combines an entity's own usage-policy decision (Phase 2/3/5's
`evaluate_*_usage()`), its normalized quality result (Step 7), and any
open duplicate/conflict groups into one deterministic per-target-use
approval decision (Step 4/5/15).

Every gate here is a hard AND: a target use is `allowed` only when
*every* independent check clears -- there is no score high enough to
outrun a blocking issue, an unresolved duplicate group, or an
unresolved conflict group. This is the structural enforcement of the
task's "a high quality score must never override a blocking issue"
rule: `evaluate_target_approval` never reads an overall score to decide
`allowed`, only `is_blocked`/blocking-issue membership.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, TypedDict

from core_model.data_governance.review import blocking_issue_ids_for_target


class TargetApprovalDecision(TypedDict):
    decision: str
    decision_code: str
    blocking_issue_ids: list[str]
    warnings: list[str]
    required_actions: list[str]


def _decision(
    decision: str,
    code: str,
    blocking_issue_ids: list[str] | None = None,
    warnings: list[str] | None = None,
    required_actions: list[str] | None = None,
) -> TargetApprovalDecision:
    return {
        "decision": decision,
        "decision_code": code,
        "blocking_issue_ids": blocking_issue_ids or [],
        "warnings": warnings or [],
        "required_actions": required_actions or [],
    }


def evaluate_target_approval(
    *,
    target_use: str,
    usage_decision: dict[str, Any] | None,
    normalized_issues: list[dict[str, Any]],
    open_duplicate_group: bool = False,
    open_conflict_group: bool = False,
    review_item_open: bool = False,
) -> TargetApprovalDecision:
    """`normalized_issues` is a list of already-persisted
    `governance_review_issues` rows (public_id, is_blocking,
    blocking_targets, severity, issue_code) for this entity's current
    review item, if any."""

    warnings: list[str] = []
    required_actions: list[str] = []

    if usage_decision is not None and not usage_decision.get("allowed"):
        return _decision(
            "blocked",
            usage_decision.get("decision_code", "BLOCKED_RIGHTS"),
            warnings=list(usage_decision.get("warnings") or []),
            required_actions=list(usage_decision.get("required_actions") or []),
        )

    blocking_ids = blocking_issue_ids_for_target(normalized_issues, target_use)
    if blocking_ids:
        return _decision(
            "blocked",
            "BLOCKED_QUALITY_ISSUE",
            blocking_issue_ids=blocking_ids,
            required_actions=["Resolve the blocking quality issue(s) before this target use."],
        )

    if open_duplicate_group:
        return _decision(
            "blocked",
            "BLOCKED_UNRESOLVED_DUPLICATE",
            required_actions=["Resolve the open duplicate group before this target use."],
        )

    if open_conflict_group:
        return _decision(
            "blocked",
            "BLOCKED_UNRESOLVED_CONFLICT",
            required_actions=["Resolve the open conflict group before this target use."],
        )

    if usage_decision is not None:
        warnings.extend(usage_decision.get("warnings") or [])
        required_actions.extend(usage_decision.get("required_actions") or [])

    non_blocking_issues = [
        issue
        for issue in normalized_issues
        if not issue.get("is_blocking") and issue.get("severity") in ("warning", "error")
    ]
    if non_blocking_issues:
        warnings.append("non_blocking_quality_issues_present")

    if review_item_open:
        return _decision(
            "needs_review",
            "REVIEW_IN_PROGRESS",
            warnings=warnings,
            required_actions=[*required_actions, "Complete the open governance review."],
        )

    return _decision("allowed", "ALLOWED", warnings=warnings, required_actions=required_actions)


def is_approval_expired(expires_at: str | None, *, now: datetime | None = None) -> bool:
    if not expires_at:
        return False
    try:
        expiry = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    reference = now or datetime.now(UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    return expiry <= reference


__all__ = ["TargetApprovalDecision", "evaluate_target_approval", "is_approval_expired"]
