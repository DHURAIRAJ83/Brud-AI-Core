"""Configurable release-approval policy.

Minimum for limited local development is one admin approval; the
recommended stricter policy requires technical + evaluation + release
roles. Blocking candidates can never be approved, warning approvals
always require a comment, and approvals become stale the moment the
underlying eligibility/manifest evidence changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApprovalPolicy:
    required_roles: tuple[str, ...] = ("release",)
    allow_self_approval: bool = True


def is_policy_satisfied(approvals: list[dict[str, Any]], policy: ApprovalPolicy) -> dict[str, Any]:
    latest_by_role: dict[str, dict[str, Any]] = {}
    for approval in approvals:
        latest_by_role[approval["role"]] = approval

    missing_roles = [role for role in policy.required_roles if role not in latest_by_role]
    has_rejection = any(
        approval["decision"] in {"reject", "request_changes"}
        for approval in latest_by_role.values()
    )
    satisfied = not missing_roles and not has_rejection and bool(latest_by_role)
    return {
        "satisfied": satisfied,
        "missing_roles": missing_roles,
        "has_rejection": has_rejection,
        "latest_by_role": {role: approval["decision"] for role, approval in latest_by_role.items()},
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
    if is_self_approval and not policy.allow_self_approval:
        violations.append("self_approval_not_allowed")
    return violations
