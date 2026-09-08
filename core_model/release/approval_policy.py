"""Configurable release-approval policy.

Minimum for limited local development is one admin approval; the
recommended stricter policy requires technical + evaluation + release
roles. Blocking candidates can never be approved, warning approvals
always require a comment, and approvals become stale the moment the
underlying eligibility/manifest evidence changes.

`role` is a self-declared approval-category label, not a verified
authorization attribute (Brud AI does not implement RBAC) -- a role
being present therefore proves nothing about who submitted it.
`minimum_distinct_approvers` is a separate, independent guarantee: at
least that many distinct `admin_public_id` identities must have
submitted an approving decision for a required role, so a single admin
cannot satisfy a multi-role policy by submitting every role themselves.

GOV-33: a candidate's or assignment's own creator can never approve it,
under any configuration. `ApprovalPolicy.allow_self_approval` (and the
`release_allow_self_approval` / `inference_assignment_allow_self_approval`
settings that feed it) are retained as configuration surface but have no
effect on this decision -- self-approval is rejected unconditionally by
`validate_approval_submission()`.

Distinct-approver counting deliberately spans every approving
submission for a required role, not only the current (latest) one per
role -- role coverage (`missing_roles`) and rejection detection
(`has_rejection`) are still governed purely by the latest submission per
role, since those describe the role's *current* state, but distinctness
answers a different, cumulative question ("how many separate people have
ever backed this role"), which the single latest-submission slot cannot
represent once more than one identity is required for one role. A
superseded approval still counts toward distinctness as long as it was
itself an approving decision; a rejecting decision never does, and
resubmission by the same admin never counts twice (a `set` of
`admin_public_id`s is inherently duplicate-free).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_APPROVING_DECISIONS = {"approve", "approve_with_warning"}


@dataclass(frozen=True)
class ApprovalPolicy:
    required_roles: tuple[str, ...] = ("release",)
    allow_self_approval: bool = True
    minimum_distinct_approvers: int = 1


def resolve_minimum_distinct_approvers(required_roles: tuple[str, ...], floor: int) -> int:
    """GOV-26 / GOV-26b: the distinct-approver minimum scales with the
    number of required roles, but never drops below the configured
    floor -- `max(floor, len(required_roles))`. 1 required role stays at
    the floor; a role count above the floor raises the minimum to match."""

    return max(floor, len(required_roles))


def is_policy_satisfied(approvals: list[dict[str, Any]], policy: ApprovalPolicy) -> dict[str, Any]:
    latest_by_role: dict[str, dict[str, Any]] = {}
    for approval in approvals:
        latest_by_role[approval["role"]] = approval

    missing_roles = [role for role in policy.required_roles if role not in latest_by_role]
    has_rejection = any(
        approval["decision"] in {"reject", "request_changes"}
        for approval in latest_by_role.values()
    )
    distinct_approver_ids = {
        approval["admin_public_id"]
        for approval in approvals
        if approval["role"] in policy.required_roles
        and approval["decision"] in _APPROVING_DECISIONS
    }
    distinct_approver_count = len(distinct_approver_ids)
    meets_minimum_distinct_approvers = distinct_approver_count >= policy.minimum_distinct_approvers
    satisfied = (
        not missing_roles
        and not has_rejection
        and bool(latest_by_role)
        and meets_minimum_distinct_approvers
    )
    return {
        "satisfied": satisfied,
        "missing_roles": missing_roles,
        "has_rejection": has_rejection,
        "latest_by_role": {role: approval["decision"] for role, approval in latest_by_role.items()},
        "distinct_approver_count": distinct_approver_count,
        "minimum_distinct_approvers": policy.minimum_distinct_approvers,
        "meets_minimum_distinct_approvers": meets_minimum_distinct_approvers,
    }


def is_approval_stale(
    *,
    approval_eligibility_checksum: str,
    current_eligibility_checksum: str,
    approval_manifest_checksum: str | None,
    current_manifest_checksum: str | None,
) -> bool:
    if approval_eligibility_checksum != current_eligibility_checksum:
        return True
    if approval_manifest_checksum is not None and current_manifest_checksum is not None:
        return approval_manifest_checksum != current_manifest_checksum
    return False


def validate_approval_submission(
    *,
    decision: str,
    comment: str,
    candidate_status_is_blocked: bool,
    is_self_approval: bool,
    policy: ApprovalPolicy,
) -> list[str]:
    violations: list[str] = []
    if candidate_status_is_blocked and decision in {"approve", "approve_with_warning"}:
        violations.append("blocking_candidate_cannot_be_approved")
    if decision == "approve_with_warning" and not comment.strip():
        violations.append("warning_approval_requires_comment")
    # GOV-33: absolute, non-overridable prohibition. `policy.allow_self_approval`
    # is deliberately not consulted here -- no configuration value can ever
    # permit a candidate's/assignment's own creator to approve it.
    if is_self_approval:
        violations.append("self_approval_not_allowed")
    return violations
