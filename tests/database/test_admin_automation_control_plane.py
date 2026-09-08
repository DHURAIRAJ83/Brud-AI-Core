"""Phase 10: Admin Automation & Control Plane.

Repository audit (see the Phase 10 final report) found NO existing
automation/scheduler subsystem anywhere in this codebase (no Celery/
APScheduler/cron dependency, no automation/schedule/trigger/rule table,
`core_model/training/scheduler.py` is an unrelated LR scheduler). Per
the phase's own explicit instruction ("DO NOT immediately introduce a
background scheduler... implement the smallest safe CONTROL-PLANE
foundation"), this phase adds NO scheduler, NO worker, NO new table,
and NO autonomous execution -- only:

- one new `ActionDefinition` (`admin_automation_define`, risk_level=
  "moderate") whose executor validates the definition and never invokes
  `target_action_type` -- reusing the *existing*
  `AdminAssistantService.propose()`/`review()`/`execute()` pipeline and
  `admin_approvals` table verbatim (`target_type='admin_automation'`
  rows *are* the durable automation-definition records; no separate
  persistence model).
- one new pure-read repository method
  (`AdminApprovalRepository.list_by_target_type()`) and two thin
  `AdminAssistantService` wrapper methods (`list_automations()`/
  `get_automation()`), mirroring the existing `list_proposals()`/
  `get_proposal()` exactly.
- two new READ_ONLY Admin Assistant tools (`list_automations`,
  `get_automation`), RBAC-gated exactly like every other tool.

No autonomous execution occurs anywhere in this phase: the executor's
only job is validation + a confirmation record.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.phase2 import AdminApprovalRepository
from backend.models.domain import AdminApprovalCreate
from backend.services.admin_assistant_service import AdminAssistantError, AdminAssistantService
from backend.services.admin_assistant_tool_governance import ToolAuthorizationError, ToolCapability
from backend.services.admin_assistant_tools import READ_ONLY_TOOLS, get_tool, run_tool
from backend.services.admin_assistant_write_governance import execute_with_governance, propose_with_governance
from core_model.admin_assistant.action_registry import ACTION_DEFINITIONS, is_known_action_type

SUPER_ADMIN_ID = "e0000000-0000-0000-0000-00000000000e"
ADMIN_ONLY_ID = "f0000000-0000-0000-0000-00000000000f"  # unmapped -> default ADMIN role
AUDITOR_ID = "a1000000-0000-0000-0000-00000000000a"
NONE_ID = "a2000000-0000-0000-0000-00000000000a"
REVIEWER_ID = "a3000000-0000-0000-0000-00000000000a"  # distinct reviewer, not otherwise privileged

_OVERRIDES = f"{SUPER_ADMIN_ID}:SUPER_ADMIN,{AUDITOR_ID}:AUDITOR,{NONE_ID}:NONE,{REVIEWER_ID}:ADMIN"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "phase10.db",
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


def _payload(target_action_type: str = "dataset_record_review", **overrides) -> dict:
    payload = {
        "name": "Test automation",
        "description": "A test automation definition",
        "target_action_type": target_action_type,
        "target_type": "dataset_record",
        "target_public_id": "dataset-record-target",
        "target_action_parameters": {"decision": "approve", "comments": "automation review"},
        "schedule_description": "every day at 09:00",
        "reason": "test coverage",
    }
    payload.update(overrides)
    return payload


def _propose_and_approve(
    service: AdminAssistantService,
    *,
    target_public_id: str,
    requested_by: str = SUPER_ADMIN_ID,
    reviewed_by: str = REVIEWER_ID,
    payload_overrides: dict | None = None,
):
    proposal = propose_with_governance(
        service,
        action_type="admin_automation_define",
        target_type="admin_automation",
        target_public_id=target_public_id,
        request_payload=_payload(**(payload_overrides or {})),
        requested_by=requested_by,
        summary="test automation",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=reviewed_by, comment=None)
    return proposal


# --- 0: action registered, wired, tool census ------------------------------


def test_action_definition_and_executor_are_registered() -> None:
    from backend.services.admin_assistant_service import ACTION_EXECUTORS

    assert "admin_automation_define" in ACTION_EXECUTORS
    assert is_known_action_type("admin_automation_define")
    definitions = {a.action_type: a for a in ACTION_DEFINITIONS}
    assert definitions["admin_automation_define"].risk_level == "moderate"
    assert definitions["admin_automation_define"].target_type == "admin_automation"


def test_new_tools_are_read_only_and_registered() -> None:
    assert len(READ_ONLY_TOOLS) == 108  # Phase 11 added get_automation_execution_readiness
    for name in ("list_automations", "get_automation"):
        tool = get_tool(name)
        assert tool is not None
        assert tool.capability is ToolCapability.READ_ONLY
        assert tool.needs_admin_id is False
        assert tool.pool_aware is False


# --- 1/2/3/4: validation / malformed definition / unknown action ----------


def test_valid_automation_definition_is_accepted(service: AdminAssistantService) -> None:
    proposal = _propose_and_approve(service, target_public_id="auto-valid")
    executed = execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    assert executed.execution_status == "succeeded"
    assert executed.execution_result["status"] == "defined"


@pytest.mark.parametrize(
    "overrides,expected_message_fragment",
    [
        ({"target_action_type": "totally_made_up_action"}, "not a known governed action"),
        ({"target_action_type": ""}, "required"),
        ({"target_action_type": None}, "required"),
        ({"target_action_parameters": "not-a-dict"}, "must be an object"),
        ({"schedule_description": "   "}, "required"),
        ({"schedule_description": None}, "required"),
    ],
)
def test_malformed_definitions_are_rejected_at_execute_time(
    service: AdminAssistantService, overrides: dict, expected_message_fragment: str
) -> None:
    proposal = _propose_and_approve(
        service, target_public_id=f"auto-malformed-{hash(frozenset(overrides.items())) & 0xFFFF}",
        payload_overrides=overrides,
    )
    with pytest.raises(Exception) as excinfo:
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    assert expected_message_fragment in str(excinfo.value)
    # Failure is recorded, not silently swallowed.
    reloaded = service.get_proposal(proposal.public_id)
    assert reloaded.execution_status == "failed"


def test_recursive_self_targeting_automation_is_rejected(service: AdminAssistantService) -> None:
    proposal = _propose_and_approve(
        service, target_public_id="auto-recursive",
        payload_overrides={"target_action_type": "admin_automation_define"},
    )
    with pytest.raises(Exception, match="no automation loops"):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


def test_capability_mismatch_read_only_tool_name_is_rejected(service: AdminAssistantService) -> None:
    """A READ_ONLY tool name is not a governed ActionDefinition -- the
    two namespaces never overlap, so referencing one as target_action_type
    is caught by the same is_known_action_type() check."""

    proposal = _propose_and_approve(
        service, target_public_id="auto-capability-mismatch",
        payload_overrides={"target_action_type": "get_dashboard_overview"},
    )
    with pytest.raises(Exception, match="not a known governed action"):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


def test_blocked_action_substring_is_rejected(service: AdminAssistantService) -> None:
    proposal = _propose_and_approve(
        service, target_public_id="auto-blocked",
        payload_overrides={"target_action_type": "start_pretraining_job"},
    )
    with pytest.raises(Exception):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


# --- 5/6/7/8: RBAC ------------------------------------------------------------


def test_none_role_cannot_propose_automation(service: AdminAssistantService) -> None:
    with pytest.raises(ToolAuthorizationError):
        propose_with_governance(
            service, action_type="admin_automation_define", target_type="admin_automation",
            target_public_id="auto-none-denied", request_payload=_payload(),
            requested_by=NONE_ID, summary="x",
        )


def test_auditor_cannot_propose_automation(service: AdminAssistantService) -> None:
    with pytest.raises(ToolAuthorizationError):
        propose_with_governance(
            service, action_type="admin_automation_define", target_type="admin_automation",
            target_public_id="auto-auditor-denied", request_payload=_payload(),
            requested_by=AUDITOR_ID, summary="x",
        )


def test_admin_role_can_propose_but_not_execute(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-admin-propose", request_payload=_payload(),
        requested_by=ADMIN_ONLY_ID, summary="x",
    )
    assert proposal.status == "pending"
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    with pytest.raises(ToolAuthorizationError):
        execute_with_governance(service, proposal.public_id, executor_public_id=ADMIN_ONLY_ID)


def test_super_admin_can_propose_and_execute(service: AdminAssistantService) -> None:
    proposal = _propose_and_approve(service, target_public_id="auto-super-admin")
    executed = execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    assert executed.execution_status == "succeeded"


def test_none_role_cannot_read_automations_via_tools(settings: Settings) -> None:
    with pytest.raises(ToolAuthorizationError):
        run_tool("list_automations", settings, {}, admin_id=NONE_ID)
    with pytest.raises(ToolAuthorizationError):
        run_tool("get_automation", settings, {"public_id": "whatever"}, admin_id=NONE_ID)


def test_auditor_can_read_automations_via_tools(settings: Settings) -> None:
    result = run_tool("list_automations", settings, {}, admin_id=AUDITOR_ID)
    assert result["available"] is True


# --- 9: approval requirement -------------------------------------------------


def test_execution_requires_approval_first(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-not-approved", request_payload=_payload(),
        requested_by=SUPER_ADMIN_ID, summary="x",
    )
    with pytest.raises(AdminAssistantError, match="must be approved"):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


# --- 10: rejected ("disabled" has no separate concept this phase) ----------


def test_rejected_automation_proposal_cannot_be_executed(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-rejected", request_payload=_payload(),
        requested_by=SUPER_ADMIN_ID, summary="x",
    )
    service.review(proposal.public_id, decision="rejected", reviewed_by=REVIEWER_ID, comment="no")
    with pytest.raises(AdminAssistantError, match="must be approved"):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


# --- 11: expiry ---------------------------------------------------------------


def test_expired_automation_proposal_cannot_be_approved(settings: Settings) -> None:
    repository = AdminApprovalRepository(settings.resolved_database_path)
    created = repository.create(
        AdminApprovalCreate(
            action_type="admin_automation_define",
            target_type="admin_automation",
            target_public_id="auto-expired",
            request_payload=_payload(),
            requested_by=SUPER_ADMIN_ID,
            summary="x",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    service = AdminAssistantService(settings)
    with pytest.raises(AdminAssistantError):
        service.review(created.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)


# --- 12: cancellation ----------------------------------------------------------


def test_pending_automation_proposal_can_be_cancelled(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-cancel", request_payload=_payload(),
        requested_by=SUPER_ADMIN_ID, summary="x",
    )
    cancelled = service.cancel(proposal.public_id, cancelled_by=SUPER_ADMIN_ID, reason="no longer needed")
    assert cancelled.status == "cancelled"
    with pytest.raises(AdminAssistantError):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


# --- 13: stale definitions -- N/A (no pre-existing target state) -----------


def test_no_stale_check_fingerprint_registered_for_automation_define() -> None:
    """Documents the design decision (not a gap): admin_automation_define
    creates a NEW entity with no prior state to go stale against, unlike
    e.g. governance_target_approval_override -- so no fingerprint
    function is registered for it, and none is needed."""

    from backend.services.admin_assistant_service import STALE_CHECK_FINGERPRINTS

    assert "admin_automation_define" not in STALE_CHECK_FINGERPRINTS


# --- 14: target action disappearance/change is caught at execute time -----


def test_target_action_type_is_revalidated_at_execute_time_not_only_propose_time(
    service: AdminAssistantService,
) -> None:
    """propose() never inspects the payload's target_action_type (only
    the outer admin_automation_define action_type) -- so a bad value
    is only caught when the executor runs, proving execute-time
    revalidation actually happens rather than only propose-time."""

    proposal = _propose_and_approve(
        service, target_public_id="auto-bad-at-execute",
        payload_overrides={"target_action_type": "not_a_real_action_at_all"},
    )
    assert proposal.status == "pending"  # propose succeeded despite the bad value
    with pytest.raises(Exception, match="not a known governed action"):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


# --- 15: duplicate execution protection --------------------------------------


def test_duplicate_execution_is_rejected(service: AdminAssistantService) -> None:
    proposal = _propose_and_approve(service, target_public_id="auto-duplicate-exec")
    execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    with pytest.raises(Exception, match="not awaiting execution"):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


# --- 16: recursive automation loop rejection (also covered above) ----------
# (see test_recursive_self_targeting_automation_is_rejected)


# --- 17: audit logging --------------------------------------------------------


def test_automation_lifecycle_is_fully_audited(service: AdminAssistantService) -> None:
    from backend.database.repositories.phase2 import AuditLogRepository

    proposal = _propose_and_approve(service, target_public_id="auto-audited")
    execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)

    events = AuditLogRepository(service.settings.resolved_database_path).recent(limit=50)
    event_types = {e.event_type for e in events}
    assert "admin_assistant_proposal_created" in event_types
    assert "admin_review_approved" in event_types
    assert "admin_assistant_proposal_executed" in event_types


# --- 18/19: read-only inspection tools ---------------------------------------


def test_list_automations_reflects_a_real_defined_automation(settings: Settings) -> None:
    service = AdminAssistantService(settings)
    proposal = _propose_and_approve(service, target_public_id="auto-listed")
    execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)

    listed = run_tool("list_automations", settings, {}, admin_id=ADMIN_ONLY_ID)
    assert listed["available"] is True
    public_ids = {item["public_id"] for item in listed["items"]}
    assert proposal.public_id in public_ids
    entry = next(item for item in listed["items"] if item["public_id"] == proposal.public_id)
    assert entry["execution_status"] == "succeeded"
    assert isinstance(entry["created_at"], str)  # JSON-safe, not a raw datetime


def test_get_automation_returns_full_record(settings: Settings) -> None:
    service = AdminAssistantService(settings)
    proposal = _propose_and_approve(service, target_public_id="auto-get")
    execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)

    got = run_tool("get_automation", settings, {"public_id": proposal.public_id}, admin_id=ADMIN_ONLY_ID)
    assert got["available"] is True
    assert got["public_id"] == proposal.public_id
    assert got["target_public_id"] == "auto-get"


def test_get_automation_not_found(settings: Settings) -> None:
    result = run_tool("get_automation", settings, {"public_id": "does-not-exist"}, admin_id=ADMIN_ONLY_ID)
    assert result == {"available": False, "reason": "automation not found"}


def test_get_automation_rejects_a_non_automation_proposal_public_id(
    service: AdminAssistantService, settings: Settings
) -> None:
    other = propose_with_governance(
        service, action_type="dataset_record_review", target_type="dataset_record",
        target_public_id="not-an-automation", request_payload={"decision": "approve", "comments": "x"},
        requested_by=SUPER_ADMIN_ID, summary="unrelated proposal",
    )
    result = run_tool("get_automation", settings, {"public_id": other.public_id}, admin_id=ADMIN_ONLY_ID)
    assert result == {"available": False, "reason": "automation not found"}


def test_list_automations_empty_state(settings: Settings) -> None:
    result = run_tool("list_automations", settings, {}, admin_id=ADMIN_ONLY_ID)
    assert result == {"available": True, "items": []}


# --- 20: zero production DB mutation / no autonomous execution -------------


def test_no_new_table_no_autonomous_execution_occurs(settings: Settings) -> None:
    """Cross-cutting proof: defining and approving (but never executing)
    an automation leaves training_jobs/pretraining_jobs/model_registry/
    dataset tables completely untouched -- nothing runs automatically,
    ever, in this phase."""

    import sqlite3

    def table_counts() -> dict[str, int]:
        conn = sqlite3.connect(settings.resolved_database_path)
        try:
            tables = [
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            ]
            return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}
        finally:
            conn.close()

    service = AdminAssistantService(settings)
    before = table_counts()
    proposal = _propose_and_approve(service, target_public_id="auto-no-execution")
    after_approval = table_counts()

    # Only admin_approvals (+ audit_logs) may have changed; nothing
    # domain-relevant, and definitely no dataset/training/model row.
    for table in ("training_jobs", "pretraining_jobs", "model_registry",
                  "model_release_candidates", "dataset_records", "dataset_versions"):
        assert before[table] == after_approval[table]

    execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    after_execution = table_counts()
    for table in ("training_jobs", "pretraining_jobs", "model_registry",
                  "model_release_candidates", "dataset_records", "dataset_versions"):
        assert before[table] == after_execution[table]


# --- 21: no Pool/Connection leakage -------------------------------------------


def test_new_tool_handlers_accept_no_pool_or_connection() -> None:
    import inspect

    from backend.services import admin_assistant_tools as tools_module

    for handler in (tools_module._tool_list_automations, tools_module._tool_get_automation):
        for param in inspect.signature(handler).parameters.values():
            annotation = str(param.annotation)
            assert "Pool" not in annotation and "sqlite3.Connection" not in annotation


# --- 22/23/24: no shell/system execution, no direct tool/executor bypass ---


def test_executor_contains_no_shell_or_arbitrary_execution() -> None:
    import ast
    import inspect
    import textwrap

    from backend.services.admin_assistant_service import _execute_admin_automation_define

    source = inspect.getsource(_execute_admin_automation_define)
    tree = ast.parse(textwrap.dedent(source))
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    body_without_docstring = ast.unparse(ast.Module(body=func.body[1:], type_ignores=[]))
    for forbidden in ("subprocess", "os.system", "eval(", "exec(", "run_tool("):
        assert forbidden not in body_without_docstring


def test_write_tool_still_cannot_execute_through_run_tool_after_phase10(settings: Settings) -> None:
    """admin_automation_define is a governed *action* (propose/review/
    execute), not a run_tool()-dispatchable tool -- it was never added
    to READ_ONLY_TOOLS, so it has no run_tool() surface at all."""

    from backend.services.admin_assistant_tools import get_tool

    assert get_tool("admin_automation_define") is None
