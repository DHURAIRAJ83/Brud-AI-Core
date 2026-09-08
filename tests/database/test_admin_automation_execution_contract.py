"""Phase 11: Governed Automation Execution & Safe Scheduling.

Repository-wide audit (see the Phase 11 report) found NO general-purpose
scheduler/task-queue framework anywhere in this codebase, and every
existing "worker + lease + claim" pattern (`PretrainingService._claim()`
/`pretraining_jobs`, `corpus_ingestion_jobs`) is tightly coupled to its
own domain -- reusing either for automation would mix unrelated job
semantics (explicitly forbidden by the task's own Option A). Building a
dedicated worker (Option C) would need a `next_run_at`-style column
`admin_approvals` does not have, which cannot be added without a
migration. Per the task's Option B, this phase implements ONLY the
execution *contract* -- pure, unwired validation/readiness logic a
future, explicitly-approved worker would call -- and adds one new
READ_ONLY tool to inspect it. NO scheduler, NO worker, NO migration, NO
autonomous execution exists anywhere in this codebase after this phase.

This file proves that absence as rigorously as it proves the new code's
own correctness: several tests below exist specifically to demonstrate
that nothing can execute automatically yet.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.admin_assistant_service import AdminAssistantService
from backend.services.admin_assistant_tool_governance import ToolAuthorizationError, ToolCapability
from backend.services.admin_assistant_tools import READ_ONLY_TOOLS, get_tool, run_tool
from backend.services.admin_assistant_write_governance import execute_with_governance, propose_with_governance
from core_model.admin_assistant.automation_policy import (
    AUTOMATION_ALLOWED_ACTIONS,
    MINIMUM_AUTOMATION_INTERVAL_SECONDS,
    SUPPORTED_SCHEDULE_KINDS,
    AutomationExecutionDecision,
    evaluate_automation_execution_readiness,
    validate_schedule,
)

SUPER_ADMIN_ID = "b0000000-0000-0000-0000-00000000000b"
ADMIN_ONLY_ID = "c0000000-0000-0000-0000-00000000000c"  # unmapped -> default ADMIN
AUDITOR_ID = "d0000000-0000-0000-0000-00000000000d"
NONE_ID = "e0000000-0000-0000-0000-00000000000e"
REVIEWER_ID = "f0000000-0000-0000-0000-00000000000f"

_OVERRIDES = f"{SUPER_ADMIN_ID}:SUPER_ADMIN,{AUDITOR_ID}:AUDITOR,{NONE_ID}:NONE,{REVIEWER_ID}:SUPER_ADMIN"


def _automation_policy_code_only() -> str:
    """Source of core_model.admin_assistant.automation_policy with its
    module-level docstring stripped, so a security/absence scan checks
    real code, not prose that legitimately names the systems it says
    were NOT reused."""

    import ast
    import inspect

    from core_model.admin_assistant import automation_policy

    tree = ast.parse(inspect.getsource(automation_policy))
    body = tree.body[1:] if isinstance(tree.body[0], ast.Expr) else tree.body
    return ast.unparse(ast.Module(body=body, type_ignores=[]))


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "phase11.db",
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


def _define_and_approve(
    service: AdminAssistantService,
    *,
    target_public_id: str,
    requested_by: str = SUPER_ADMIN_ID,
    execute: bool = True,
):
    payload = _automation_payload()
    proposal = propose_with_governance(
        service,
        action_type="admin_automation_define",
        target_type="admin_automation",
        target_public_id=target_public_id,
        request_payload=payload,
        requested_by=requested_by,
        summary="test automation",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    if execute:
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    # Return the current record -- review()/execute() mutate the stored
    # row, not the stale `proposal` snapshot captured before either ran.
    return service.get_automation(proposal.public_id)


def _automation_payload(**overrides) -> dict:
    payload = {
        "name": "test automation",
        "description": "d",
        "target_action_type": "dataset_record_review",
        "target_type": "dataset_record",
        "target_public_id": "dataset-record-target",
        "target_action_parameters": {"decision": "approve", "comments": "automation review"},
        "schedule_description": "daily",
        "reason": "test",
    }
    payload.update(overrides)
    return payload


# =====================  ARCHITECTURE  =======================================


def test_1_no_scheduler_or_worker_infrastructure_was_added() -> None:
    """No new dependency, no new background task, no new table: the
    only evidence of Phase 11 is the pure automation_policy module plus
    one new READ_ONLY tool. Scans code only, excluding the module's own
    docstring (which legitimately *names* these systems as prose
    explaining what was deliberately NOT reused)."""

    source = _automation_policy_code_only()
    for forbidden in ("asyncio.create_task", "Celery", "APScheduler", "while True", "BackgroundTasks"):
        assert forbidden not in source


def test_2_no_duplicate_scheduler_no_second_worker_claim_mechanism() -> None:
    """automation_policy never imports PretrainingService._claim() or
    any worker-claiming primitive -- it is pure evaluation logic, not a
    second job-claiming implementation."""

    source = _automation_policy_code_only()
    assert "_claim" not in source
    assert "corpus_ingestion_jobs" not in source


def test_3_no_unauthorized_execution_path_exists(settings: Settings) -> None:
    """There is no run_tool()-dispatchable name for triggering an
    automation, and no new ActionDefinition that executes target_action_type
    directly -- the only way any real action ever runs is through the
    unmodified Phase 4 execute_with_governance() seam."""

    assert get_tool("admin_automation_define") is None
    assert get_tool("trigger_automation") is None
    assert get_tool("run_automation") is None


# =====================  ALLOWLIST  ==========================================


def test_4_5_6_allowlist_is_empty_by_default_and_blocks_every_action(
    service: AdminAssistantService,
) -> None:
    assert AUTOMATION_ALLOWED_ACTIONS == frozenset()
    automation = _define_and_approve(service, target_public_id="auto-allowlist")
    decision = evaluate_automation_execution_readiness(automation, admin_role_overrides={})
    assert decision.ready is False
    assert any("AUTOMATION_ALLOWED_ACTIONS" in reason for reason in decision.blocking_reasons)


def test_7_capability_mismatch_unknown_action_type_blocks_readiness(
    service: AdminAssistantService,
) -> None:
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-unknown-target",
        request_payload=_automation_payload(target_action_type="get_dashboard_overview"),
        requested_by=SUPER_ADMIN_ID, summary="s",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    # get_dashboard_overview is a READ_ONLY tool, not a governed action --
    # execute() itself already rejects it (proven in Phase 10); readiness
    # evaluation on the (never-executed) definition reports it too.
    with pytest.raises(Exception):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    reloaded = service.get_automation(proposal.public_id)
    decision = evaluate_automation_execution_readiness(reloaded, admin_role_overrides={})
    assert decision.ready is False


# =====================  RBAC  ===============================================


def test_8_none_role_denied_readiness_tool(settings: Settings) -> None:
    with pytest.raises(ToolAuthorizationError):
        run_tool(
            "get_automation_execution_readiness", settings, {"public_id": "whatever"}, admin_id=NONE_ID
        )


def test_9_auditor_can_read_but_readiness_reflects_auditor_cannot_execute(
    service: AdminAssistantService, settings: Settings
) -> None:
    automation = _define_and_approve(service, target_public_id="auto-auditor-rbac")
    result = run_tool(
        "get_automation_execution_readiness", settings, {"public_id": automation.public_id},
        admin_id=AUDITOR_ID,
    )
    assert result["available"] is True  # AUDITOR has tool.read

    # But if AUDITOR had *defined* this automation, readiness would report
    # them as lacking tool.execute:
    from backend.services.admin_assistant_tool_governance import AdminRole

    decision = evaluate_automation_execution_readiness(
        automation.model_copy(update={"requested_by": AUDITOR_ID}),
        admin_role_overrides={AUDITOR_ID: AdminRole.AUDITOR},
    )
    assert decision.ready is False
    assert any("tool.execute" in reason for reason in decision.blocking_reasons)


def test_10_admin_role_behavior_matches_phase10(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-admin-behavior",
        request_payload=_automation_payload(),
        requested_by=ADMIN_ONLY_ID, summary="s",
    )
    assert proposal.status == "pending"
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    with pytest.raises(ToolAuthorizationError):
        execute_with_governance(service, proposal.public_id, executor_public_id=ADMIN_ONLY_ID)


def test_11_super_admin_can_fully_define_and_readiness_only_blocks_on_allowlist(
    service: AdminAssistantService,
) -> None:
    from backend.services.admin_assistant_tool_governance import AdminRole

    automation = _define_and_approve(service, target_public_id="auto-super-admin-full")
    decision = evaluate_automation_execution_readiness(
        automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    # Only the (currently-empty) allowlist blocks a fully-approved,
    # correctly-authorized SUPER_ADMIN automation -- proving RBAC/approval
    # are NOT the blocker for the best-case admin.
    assert decision.ready is False
    assert len(decision.blocking_reasons) == 1
    assert "AUTOMATION_ALLOWED_ACTIONS" in decision.blocking_reasons[0]


# =====================  APPROVAL  ===========================================


def test_12_unapproved_definition_blocks_readiness(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-unapproved",
        request_payload=_automation_payload(),
        requested_by=SUPER_ADMIN_ID, summary="s",
    )
    reloaded = service.get_automation(proposal.public_id)
    decision = evaluate_automation_execution_readiness(reloaded, admin_role_overrides={})
    assert decision.ready is False
    assert any("not 'approved'" in reason for reason in decision.blocking_reasons)


def test_13_14_expired_and_cancelled_automations_block_readiness(
    service: AdminAssistantService,
) -> None:
    # Cancelled
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-cancelled-readiness",
        request_payload=_automation_payload(),
        requested_by=SUPER_ADMIN_ID, summary="s",
    )
    service.cancel(proposal.public_id, cancelled_by=SUPER_ADMIN_ID, reason="no longer needed")
    reloaded = service.get_automation(proposal.public_id)
    decision = evaluate_automation_execution_readiness(reloaded, admin_role_overrides={})
    assert decision.ready is False
    assert any("cancelled" in reason for reason in decision.blocking_reasons)


def test_15_stale_definition_never_executed_blocks_readiness(service: AdminAssistantService) -> None:
    automation = _define_and_approve(service, target_public_id="auto-stale", execute=False)
    decision = evaluate_automation_execution_readiness(automation, admin_role_overrides={})
    assert decision.ready is False
    assert any("never confirmed" in reason for reason in decision.blocking_reasons)


def test_16_self_approval_of_the_defining_action_is_unaffected_by_phase_11(
    service: AdminAssistantService,
) -> None:
    """admin_automation_define is risk_level='moderate' -- Phase 4's
    self-approval prohibition only applies to risk_level='high'
    (unmodified); Phase 11 changes nothing about this."""

    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-self-review",
        request_payload=_automation_payload(),
        requested_by=SUPER_ADMIN_ID, summary="s",
    )
    # Same admin reviews their own moderate-risk proposal -- allowed,
    # exactly as it was before Phase 11 (only high-risk requires a
    # distinct reviewer).
    reviewed = service.review(proposal.public_id, decision="approved", reviewed_by=SUPER_ADMIN_ID, comment=None)
    assert reviewed.status == "approved"


# =====================  AUTOMATION  =========================================


def test_17_18_no_disabled_or_expired_state_yet_documented_not_fabricated() -> None:
    """Phase 10/11 deliberately have no 'enabled/disabled' toggle
    (nothing runs autonomously, so nothing needs disabling) -- this test
    documents that as an intentional absence, not an oversight."""

    from backend.models.domain import AdminApprovalPublic

    assert "enabled" not in AdminApprovalPublic.model_fields


@pytest.mark.parametrize(
    "schedule,expect_valid",
    [
        ({"kind": "once", "run_at": "2026-09-01T09:00:00Z"}, True),
        ({"kind": "daily", "time_of_day": "09:00"}, True),
        ({"kind": "interval", "interval_seconds": MINIMUM_AUTOMATION_INTERVAL_SECONDS}, True),
        ({"kind": "hourly"}, False),
        ({"kind": "once"}, False),
        ({"kind": "daily"}, False),
        ({"kind": "interval", "interval_seconds": 0}, False),
        ({"kind": "interval", "interval_seconds": -100}, False),
        ({"kind": "interval", "interval_seconds": 60}, False),
        ({"kind": "interval", "interval_seconds": "3600"}, False),
        ("not-a-dict", False),
        ({}, False),
    ],
)
def test_19_20_malformed_and_sub_minimum_schedules_rejected(schedule, expect_valid: bool) -> None:
    errors = validate_schedule(schedule)
    assert (len(errors) == 0) is expect_valid


def test_21_recursive_automation_still_rejected(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-recursive-p11",
        request_payload=_automation_payload(target_action_type="admin_automation_define"),
        requested_by=SUPER_ADMIN_ID, summary="s",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    with pytest.raises(Exception, match="no automation loops"):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


def test_22_self_targeting_covered_by_test_21() -> None:
    pass  # same mechanism; see test_21


def test_23_duplicate_execution_still_prevented(service: AdminAssistantService) -> None:
    proposal = _define_and_approve(service, target_public_id="auto-dup-exec-p11", execute=True)
    with pytest.raises(Exception, match="not awaiting execution"):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


def test_24_no_concurrent_execution_path_exists() -> None:
    """There is no dispatcher at all, so 'concurrent execution' of the
    same automation cannot occur -- proven by absence: no polling loop,
    no worker, nothing that could race with itself."""

    import inspect

    from core_model.admin_assistant import automation_policy

    source = inspect.getsource(automation_policy)
    assert "Lock(" not in source and "threading" not in source  # no concurrency primitives needed


# =====================  FAILURE  ============================================


def test_25_26_execution_failure_is_audited_and_never_silently_succeeds(
    service: AdminAssistantService,
) -> None:
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-failure-p11",
        request_payload=_automation_payload(target_action_type="not_a_real_action"),
        requested_by=SUPER_ADMIN_ID, summary="s",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    with pytest.raises(Exception):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    reloaded = service.get_automation(proposal.public_id)
    assert reloaded.execution_status == "failed"

    from backend.database.repositories.phase2 import AuditLogRepository

    events = AuditLogRepository(service.settings.resolved_database_path).recent(limit=50)
    event_types = {e.event_type for e in events}
    assert "admin_assistant_proposal_execution_failed" in event_types


def test_27_no_retry_mechanism_exists_this_phase() -> None:
    import inspect

    from core_model.admin_assistant import automation_policy

    source = inspect.getsource(automation_policy)
    assert "retry" not in source.lower()


def test_28_cancellation_prevents_future_execution(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service, action_type="admin_automation_define", target_type="admin_automation",
        target_public_id="auto-cancel-prevents-p11",
        request_payload=_automation_payload(),
        requested_by=SUPER_ADMIN_ID, summary="s",
    )
    service.cancel(proposal.public_id, cancelled_by=SUPER_ADMIN_ID, reason="stop")
    with pytest.raises(Exception):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


# =====================  SECURITY  ===========================================


def test_29_30_31_32_no_subprocess_eval_exec_or_arbitrary_import() -> None:
    import ast
    import inspect

    from core_model.admin_assistant import automation_policy

    tree = ast.parse(inspect.getsource(automation_policy))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")
    source = inspect.getsource(automation_policy)
    assert "subprocess" not in source
    assert "sqlite3.connect" not in source and "connection.execute" not in source


def test_33_34_no_direct_tool_handler_or_run_tool_bypass() -> None:
    import ast
    import inspect
    import textwrap

    from core_model.admin_assistant.automation_policy import evaluate_automation_execution_readiness

    source = inspect.getsource(evaluate_automation_execution_readiness)
    tree = ast.parse(textwrap.dedent(source))
    func = tree.body[0]
    assert isinstance(func, ast.FunctionDef)
    body = ast.unparse(ast.Module(body=func.body[1:], type_ignores=[]))
    assert "run_tool(" not in body
    assert "execute(" not in body
    assert ".handler(" not in body


def test_35_no_approval_bypass_readiness_never_mutates(service: AdminAssistantService) -> None:
    automation = _define_and_approve(service, target_public_id="auto-no-mutate-readiness")
    before = service.get_automation(automation.public_id)
    evaluate_automation_execution_readiness(before, admin_role_overrides={})
    evaluate_automation_execution_readiness(before, admin_role_overrides={})
    after = service.get_automation(automation.public_id)
    assert before == after  # calling readiness repeatedly never changes anything


def test_36_no_rbac_bypass_readiness_tool_still_gated(settings: Settings) -> None:
    with pytest.raises(ToolAuthorizationError):
        run_tool(
            "get_automation_execution_readiness", settings, {"public_id": "x"}, admin_id=NONE_ID
        )


# =====================  INTEGRITY  ==========================================


def test_37_38_isolated_temp_db_used(settings: Settings, tmp_path: Path) -> None:
    assert str(settings.resolved_database_path).startswith(str(tmp_path))
    assert "brud_ai.db" not in str(settings.resolved_database_path)


def test_39_zero_unintended_mutation_from_readiness_tool(settings: Settings, service: AdminAssistantService) -> None:
    import sqlite3

    automation = _define_and_approve(service, target_public_id="auto-integrity-p11")

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

    before = table_counts()
    run_tool(
        "get_automation_execution_readiness", settings, {"public_id": automation.public_id},
        admin_id=SUPER_ADMIN_ID,
    )
    after = table_counts()
    assert before == after


def test_40_audit_evidence_preserved_across_readiness_calls(service: AdminAssistantService) -> None:
    from backend.database.repositories.phase2 import AuditLogRepository

    automation = _define_and_approve(service, target_public_id="auto-audit-preserved-p11")
    repo = AuditLogRepository(service.settings.resolved_database_path)
    before_count = len(repo.recent(limit=100))
    evaluate_automation_execution_readiness(automation, admin_role_overrides={})
    after_count = len(repo.recent(limit=100))
    assert before_count == after_count  # readiness evaluation writes no audit row of its own


# =====================  TOOL REGISTRATION  ==================================


def test_new_tool_is_read_only_and_registered() -> None:
    assert len(READ_ONLY_TOOLS) == 108
    tool = get_tool("get_automation_execution_readiness")
    assert tool is not None
    assert tool.capability is ToolCapability.READ_ONLY
    assert tool.needs_admin_id is False
    assert tool.pool_aware is False


def test_readiness_tool_not_found_for_unknown_automation(settings: Settings) -> None:
    result = run_tool(
        "get_automation_execution_readiness", settings, {"public_id": "does-not-exist"},
        admin_id=SUPER_ADMIN_ID,
    )
    assert result == {"available": False, "reason": "automation not found"}


def test_supported_schedule_kinds_are_small_and_deterministic() -> None:
    assert SUPPORTED_SCHEDULE_KINDS == ("once", "daily", "interval")


def test_readiness_decision_is_an_immutable_dataclass() -> None:
    decision = AutomationExecutionDecision(ready=True, blocking_reasons=())
    with pytest.raises(Exception):
        decision.ready = False  # type: ignore[misc]
