"""Per-record, per-target-pipeline eligibility decision (Step 4's
preflight combinator + Step 5's legacy policy).

Never re-implements Phase 6's rights/quality/duplicate/conflict gating
-- it combines an already-computed Phase 6 `TargetApprovalDecision`
(`GovernanceApprovalService.evaluate()`'s return shape) with build-
specific signals (legacy classification, prior duplicate export for
this exact target, cross-build evaluation-isolation) into one final
per-record decision. Every reason is explicit; there is no single
aggregate boolean (rule: "Return explicit reasons for every blocked
record. Do not use one aggregate boolean without detailed decisions.").
"""

from __future__ import annotations

from typing import Any, TypedDict

from core_model.pipeline_integration import LEGACY_UNCLASSIFIED_STATUS


class RecordEligibility(TypedDict):
    decision: str
    decision_code: str
    blocking_reasons: list[str]
    warnings: list[str]
    is_legacy: bool


def _decision(
    decision: str,
    code: str,
    blocking_reasons: list[str] | None = None,
    warnings: list[str] | None = None,
    *,
    is_legacy: bool = False,
) -> RecordEligibility:
    return {
        "decision": decision,
        "decision_code": code,
        "blocking_reasons": blocking_reasons or [],
        "warnings": warnings or [],
        "is_legacy": is_legacy,
    }


def is_legacy_record(*, has_review_item: bool, has_any_target_approval: bool) -> bool:
    """A record with zero governance activity at all (Step 5) -- never
    inferred from anything else, only the literal absence of both a
    review item and any target-approval decision ever recorded."""

    return not has_review_item and not has_any_target_approval


def decide_pipeline_eligibility(
    *,
    target_pipeline: str,
    governance_decision: dict[str, Any],
    is_legacy: bool,
    legacy_override_reason: str | None = None,
    already_exported_for_target: bool = False,
    excluded_by_evaluation_isolation: bool = False,
) -> RecordEligibility:
    """`governance_decision` is the dict `GovernanceApprovalService
    .evaluate()`/`.status()` already returns:
    `{decision, decision_code, blocking_issue_ids/blocking_reasons,
    warnings, required_actions}`. This function never overrides a
    Phase 6 `blocked` decision -- a legacy override only ever affects
    the *legacy_unclassified* gate, never a genuine rights/quality/
    duplicate/conflict block."""

    if already_exported_for_target:
        return _decision(
            "excluded",
            "ALREADY_EXPORTED_FOR_TARGET",
            [f"record was already exported for {target_pipeline}"],
        )

    if excluded_by_evaluation_isolation:
        return _decision(
            "excluded",
            "EVALUATION_ISOLATION",
            ["record was already included in an evaluation-target build "
             "and must never enter a training split"],
        )

    if is_legacy and not legacy_override_reason:
        return _decision(
            "blocked",
            LEGACY_UNCLASSIFIED_STATUS.upper(),
            ["record has no governance review activity and is not yet classified"],
            is_legacy=True,
        )

    if governance_decision.get("decision") == "blocked":
        return _decision(
            "blocked",
            governance_decision.get("decision_code", "BLOCKED"),
            list(
                governance_decision.get("blocking_reasons")
                or governance_decision.get("blocking_issue_ids")
                or []
            ),
            list(governance_decision.get("warnings") or []),
            is_legacy=is_legacy,
        )

    if governance_decision.get("decision") == "needs_review":
        return _decision(
            "blocked",
            governance_decision.get("decision_code", "REVIEW_IN_PROGRESS"),
            ["an open governance review must be resolved first"],
            list(governance_decision.get("warnings") or []),
            is_legacy=is_legacy,
        )

    warnings = list(governance_decision.get("warnings") or [])
    if is_legacy and legacy_override_reason:
        warnings.append(f"included via legacy override: {legacy_override_reason}")

    return _decision("eligible", "ELIGIBLE", [], warnings, is_legacy=is_legacy)


__all__ = ["RecordEligibility", "is_legacy_record", "decide_pipeline_eligibility"]
