"""Phase 4: proves the RBAC boundary in front of AdminAssistantService's
propose()/execute() (`propose_with_governance`/`execute_with_governance`
in admin_assistant_write_governance.py) is wired correctly, and that it
adds permission enforcement WITHOUT bypassing, weakening, or
duplicating any existing rule inside AdminAssistantService itself:
allowlisted action_type, risk classification, stale-check fingerprints,
expiry TTL, or same-admin high-risk rejection.

Uses `governance_target_approval_override` (risk_level="high",
mirroring tests/backend/test_admin_assistant_lifecycle.py's own
pattern) as the proof action -- it needs no pre-seeded target row, so
this file stays self-contained.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.repositories.phase2 import AdminApprovalRepository
from backend.models.domain import AdminApprovalCreate
from backend.services.admin_assistant_service import AdminAssistantError, AdminAssistantService
from backend.services.admin_assistant_tool_governance import (
    ToolAuthorizationError,
    ToolCapability,
    authorize_tool_invocation,
    permissions_for_role,
)
from backend.services.admin_assistant_write_governance import (
    execute_with_governance,
    propose_with_governance,
)

SUPER_ADMIN_ID = "50000000-0000-0000-0000-000000000005"
ADMIN_ONLY_ID = "60000000-0000-0000-0000-000000000006"  # unmapped -> default ADMIN role
AUDITOR_ID = "70000000-0000-0000-0000-000000000007"
NONE_ID = "80000000-0000-0000-0000-000000000008"
REVIEWER_ID = "90000000-0000-0000-0000-000000000009"  # distinct reviewer for high-risk

_OVERRIDES = f"{SUPER_ADMIN_ID}:SUPER_ADMIN,{AUDITOR_ID}:AUDITOR,{NONE_ID}:NONE,{REVIEWER_ID}:SUPER_ADMIN"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    from backend.database.migrations import initialize_database

    settings = Settings(
        database_path=tmp_path / "write_governance.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
        admin_role_overrides=_OVERRIDES,
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def service(settings: Settings) -> AdminAssistantService:
    return AdminAssistantService(settings)


def _propose_kwargs(target_public_id: str, **payload_overrides) -> dict:
    payload = {
        "entity_type": "dataset_record",
        "target_use": "rag",
        "decision": "allowed",
        "reason": "verified manually",
    }
    payload.update(payload_overrides)
    return dict(
        action_type="governance_target_approval_override",
        target_type="governance_entity",
        target_public_id=target_public_id,
        request_payload=payload,
        summary="Override rag eligibility",
    )


# --- capability vs permission separation (reaffirmed for write governance) --


def test_capability_vs_permission_are_distinct_for_write_tools() -> None:
    """A WRITE-capability tool stays blocked through run_tool() even
    with every permission granted -- capability and permission remain
    two separate dimensions, neither alone sufficient (INVARIANT 2)."""

    from backend.services.admin_assistant_tool_governance import AdminRole

    full_perms = permissions_for_role(AdminRole.SUPER_ADMIN)
    decision = authorize_tool_invocation(
        "x", ToolCapability.WRITE, admin_id=SUPER_ADMIN_ID, permissions=full_perms
    )
    assert decision.allowed is False


# --- WRITE direct-execution denial through run_tool() (regression) ---------


def test_write_tool_still_cannot_execute_through_run_tool_after_phase4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from backend.services.admin_assistant_tools import TOOL_BY_NAME, ToolDefinition, run_tool

    def handler(settings, params):  # pragma: no cover
        return {"mutated": True}

    synthetic = ToolDefinition(
        "synthetic_phase4_write_tool", "system", "d", (), handler, capability=ToolCapability.WRITE
    )
    monkeypatch.setitem(TOOL_BY_NAME, synthetic.name, synthetic)
    with pytest.raises(ToolAuthorizationError):
        run_tool(synthetic.name, Settings(database_path=tmp_path / "unused.db"), {}, admin_id=SUPER_ADMIN_ID)


# --- ADMIN can propose, cannot execute --------------------------------------


def test_admin_can_create_a_proposal(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, requested_by=ADMIN_ONLY_ID, **_propose_kwargs("target-admin-propose")
    )
    assert proposal.status == "pending"


def test_admin_cannot_execute_even_an_approved_proposal(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, requested_by=ADMIN_ONLY_ID, **_propose_kwargs("target-admin-execute-denied")
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    with pytest.raises(ToolAuthorizationError):
        execute_with_governance(service, proposal.public_id, executor_public_id=ADMIN_ONLY_ID)
    # Never reached the executor -- still pending execution, not failed.
    reloaded = service.get_proposal(proposal.public_id)
    assert reloaded.execution_status == "pending"


# --- SUPER_ADMIN reaches execute only through the real governance path -----


def test_super_admin_governed_execution_path_end_to_end(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, requested_by=SUPER_ADMIN_ID, **_propose_kwargs("target-super-admin-e2e")
    )
    assert proposal.status == "pending"
    # High risk -- reviewer must differ from proposer regardless of role.
    reviewed = service.review(
        proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment="ok"
    )
    assert reviewed.status == "approved"
    executed = execute_with_governance(
        service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID
    )
    assert executed.execution_status == "succeeded"


def test_super_admin_still_cannot_execute_before_approval(service: AdminAssistantService) -> None:
    """SUPER_ADMIN has tool.execute, but that is permission, not
    approval state -- AdminAssistantService.execute()'s own
    status-must-be-approved rule is untouched (INVARIANT 5)."""

    proposal = propose_with_governance(
        service, requested_by=SUPER_ADMIN_ID, **_propose_kwargs("target-super-admin-preapproval")
    )
    with pytest.raises(AdminAssistantError):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


# --- AUDITOR cannot propose or execute --------------------------------------


def test_auditor_cannot_create_a_proposal(service: AdminAssistantService) -> None:
    with pytest.raises(ToolAuthorizationError):
        propose_with_governance(
            service, requested_by=AUDITOR_ID, **_propose_kwargs("target-auditor-propose-denied")
        )


def test_auditor_cannot_execute(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, requested_by=SUPER_ADMIN_ID, **_propose_kwargs("target-auditor-execute-denied")
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    with pytest.raises(ToolAuthorizationError):
        execute_with_governance(service, proposal.public_id, executor_public_id=AUDITOR_ID)


# --- NONE cannot propose or execute ------------------------------------------


def test_none_role_cannot_propose(service: AdminAssistantService) -> None:
    with pytest.raises(ToolAuthorizationError):
        propose_with_governance(
            service, requested_by=NONE_ID, **_propose_kwargs("target-none-propose-denied")
        )


def test_none_role_cannot_execute(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, requested_by=SUPER_ADMIN_ID, **_propose_kwargs("target-none-execute-denied")
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    with pytest.raises(ToolAuthorizationError):
        execute_with_governance(service, proposal.public_id, executor_public_id=NONE_ID)


# --- approval requirement / risk / stale-check / expiry stay enforced ------


def test_approval_requirement_still_enforced_for_an_authorized_executor(
    service: AdminAssistantService,
) -> None:
    proposal = propose_with_governance(
        service, requested_by=SUPER_ADMIN_ID, **_propose_kwargs("target-approval-required")
    )
    with pytest.raises(AdminAssistantError, match="must be approved"):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


def test_same_admin_high_risk_rejection_still_enforced_through_governed_propose(
    service: AdminAssistantService,
) -> None:
    proposal = propose_with_governance(
        service, requested_by=SUPER_ADMIN_ID, **_propose_kwargs("target-same-admin-rejection")
    )
    with pytest.raises(AdminAssistantError, match="distinct from"):
        service.review(
            proposal.public_id, decision="approved", reviewed_by=SUPER_ADMIN_ID, comment=None
        )


def test_stale_check_still_enforced_through_governed_propose(
    service: AdminAssistantService,
) -> None:
    from backend.services.governance_service import GovernanceApprovalService

    target_public_id = "target-stale-check"
    proposal = propose_with_governance(
        service, requested_by=SUPER_ADMIN_ID, **_propose_kwargs(target_public_id)
    )
    GovernanceApprovalService(service.settings).override(
        "dataset_record",
        target_public_id,
        "rag",
        "blocked",
        reason="licence issue found after proposing",
        admin_id=REVIEWER_ID,
    )
    with pytest.raises(AdminAssistantError, match="changed since this proposal"):
        service.review(
            proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None
        )


def test_expiry_still_enforced_for_an_authorized_executor(service: AdminAssistantService) -> None:
    repository = AdminApprovalRepository(service.settings.resolved_database_path)
    created = repository.create(
        AdminApprovalCreate(
            action_type="dataset_source_update",
            target_type="dataset_source",
            target_public_id="target-expiry-test",
            request_payload={"name": "X"},
            requested_by=SUPER_ADMIN_ID,
            summary="",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    with pytest.raises(AdminAssistantError):
        execute_with_governance(service, created.public_id, executor_public_id=SUPER_ADMIN_ID)


# --- audit logging -----------------------------------------------------------


def test_denied_proposal_and_denied_execution_are_both_audited(
    service: AdminAssistantService,
) -> None:
    with pytest.raises(ToolAuthorizationError):
        propose_with_governance(
            service, requested_by=NONE_ID, **_propose_kwargs("target-audit-propose-denied")
        )

    proposal = propose_with_governance(
        service, requested_by=SUPER_ADMIN_ID, **_propose_kwargs("target-audit-execute-denied")
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    with pytest.raises(ToolAuthorizationError):
        execute_with_governance(service, proposal.public_id, executor_public_id=NONE_ID)

    from backend.database.repositories.phase2 import AuditLogRepository

    events = AuditLogRepository(service.settings.resolved_database_path).recent(limit=50)
    event_types = {e.event_type for e in events}
    assert "admin_assistant_proposal_denied_permission" in event_types
    assert "admin_assistant_execution_denied_permission" in event_types


def test_successful_governed_execution_is_audited(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, requested_by=SUPER_ADMIN_ID, **_propose_kwargs("target-audit-success")
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)

    from backend.database.repositories.phase2 import AuditLogRepository

    events = AuditLogRepository(service.settings.resolved_database_path).recent(limit=50)
    event_types = {e.event_type for e in events}
    assert "admin_assistant_proposal_created" in event_types
    assert "admin_assistant_proposal_executed" in event_types


# --- no raw connection/pool exposure through the write governance layer ----


def test_write_governance_functions_accept_no_pool_or_connection() -> None:
    import inspect

    from backend.services import admin_assistant_write_governance as wg

    for fn in (wg.propose_with_governance, wg.execute_with_governance, wg._require_permission):
        for name, param in inspect.signature(fn).parameters.items():
            annotation = str(param.annotation)
            assert "Pool" not in annotation and "sqlite3.Connection" not in annotation


def test_write_governance_never_touches_admin_assistant_context_pool_column(
    service: AdminAssistantService,
) -> None:
    """AdminAssistantService has no `pool` attribute at all -- confirms
    this Phase 4 seam cannot leak a ConnectionPool into a mutation path
    even by accident (INVARIANT 15)."""

    assert not hasattr(service, "pool")
