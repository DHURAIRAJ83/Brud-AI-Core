"""Phase 4: the RBAC authorization boundary in front of the existing,
unmodified `AdminAssistantService.propose()`/`execute()` mutation
pipeline.

Design rationale: `AdminAssistantService.propose()`/`execute()`/
`review()` are called directly -- bypassing the HTTP API layer -- by
roughly a dozen pre-Phase-4 feature test suites (document SFT, dataset
verification, knowledge gap, incremental training, etc.) that exercise
"any authenticated admin" behavior unrelated to RBAC. Gating those
methods themselves would force a bulk edit across every one of those
unrelated suites, which the Phase 4 scope rule ("do NOT modify
unrelated infrastructure") forbids -- it would also be a second,
competing place the same decision gets made.

Instead, exactly like `run_tool()` is the authorization boundary in
front of the 90 tool handlers without those handlers themselves
knowing about RBAC, this module is the boundary in front of
`AdminAssistantService`'s real API-facing entry points
(`backend/api/routes/admin_assistant.py`'s `create_proposal`/
`execute_proposal`) -- the only two call sites wired to it.
`AdminAssistantService` itself, `AdminApprovalRepository`, risk
classification, stale-check fingerprints, expiry TTL, and same-admin
high-risk rejection are all completely unmodified: this module never
reimplements or bypasses any of them (INVARIANTS 5-9) -- it only
decides whether to call them at all, and never executes a mutation
itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.models.domain import AuditOutcome
from backend.services.admin_assistant_tool_governance import (
    Permission,
    ToolAuthorizationError,
    permissions_for_role,
    resolve_admin_role,
)

if TYPE_CHECKING:
    from backend.models.domain import AdminApprovalPublic
    from backend.services.admin_assistant_service import AdminAssistantService


def _require_permission(
    service: "AdminAssistantService",
    permission: Permission,
    *,
    admin_id: str,
    event_type: str,
    action: str,
    resource_public_id: str | None,
) -> None:
    role = resolve_admin_role(admin_id, service.settings.admin_role_overrides_map)
    permissions = permissions_for_role(role)
    if permission in permissions:
        return
    # Reuses AdminAssistantService's own audit plumbing (`_record_audit`,
    # which in turn reuses its own `AuditLogRepository` instance) rather
    # than constructing a second repository against the same database
    # path -- INVARIANT 20 (every mutation attempt, including a denied
    # one, must remain auditable) without a duplicate audit mechanism.
    service._record_audit(
        event_type=event_type,
        action=action,
        actor_reference=admin_id,
        resource_public_id=resource_public_id,
        outcome=AuditOutcome.DENIED,
        metadata={"required_permission": permission.value, "resolved_role": role.value},
    )
    raise ToolAuthorizationError(
        f"admin lacks required permission {permission.value!r} for this action"
    )


def propose_with_governance(
    service: "AdminAssistantService",
    *,
    action_type: str,
    target_type: str,
    target_public_id: str,
    request_payload: dict[str, Any],
    requested_by: str,
    summary: str,
) -> "AdminApprovalPublic":
    """INVARIANT 3: `tool.propose` controls only whether `requested_by`
    may create a proposal at all -- every existing rule inside
    `AdminAssistantService.propose()` (allowlisted action_type, blocked
    substrings, reason requirement, risk stamping, preview, stale-check
    fingerprint capture, expiry) still applies unchanged once this
    check passes."""

    _require_permission(
        service,
        Permission.TOOL_PROPOSE,
        admin_id=requested_by,
        event_type="admin_assistant_proposal_denied_permission",
        action=action_type,
        resource_public_id=None,
    )
    return service.propose(
        action_type=action_type,
        target_type=target_type,
        target_public_id=target_public_id,
        request_payload=request_payload,
        requested_by=requested_by,
        summary=summary,
    )


def execute_with_governance(
    service: "AdminAssistantService", public_id: str, *, executor_public_id: str
) -> "AdminApprovalPublic":
    """INVARIANT 4: `tool.execute` controls only whether
    `executor_public_id` may attempt to execute an *already-approved*
    proposal -- it grants nothing about approval status, risk, or
    staleness. The permission check runs before
    `AdminAssistantService.execute()` is even reached, so a caller
    without `tool.execute` learns nothing about whether `public_id`
    exists, is approved, or has already run (INVARIANT 1/2: denial is
    an authorization decision, made before any of that state is
    read)."""

    _require_permission(
        service,
        Permission.TOOL_EXECUTE,
        admin_id=executor_public_id,
        event_type="admin_assistant_execution_denied_permission",
        action="execute",
        resource_public_id=public_id,
    )
    return service.execute(public_id, executor_public_id=executor_public_id)
