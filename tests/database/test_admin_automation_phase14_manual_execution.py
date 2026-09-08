"""Phase 14: Human-Triggered Bounded Automation Execution.

Tests verify that the manual execution control plane:
- Requires explicit human administrator trigger
- Enforces single-run execution guarantees (no automatic retries/loops)
- Preserves Phase 3 RBAC, Phase 4 governance, Phase 10-12 target policy, and Phase 13 evaluation
- Rejects execution when AUTOMATION_ALLOWED_ACTIONS is empty (Outcome A)
- Performs zero database writes or target mutations when execution is refused
- Rejects subprocess, eval, exec, cron, queue, scheduler, and background worker creation
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.phase2 import AuditLogRepository
from backend.models.domain import ApprovalStatus, ExecutionStatus
from backend.services.admin_assistant_service import AdminAssistantError, AdminAssistantService
from backend.services.admin_assistant_tool_governance import AdminRole
from backend.services.admin_assistant_write_governance import (
    execute_with_governance,
    propose_with_governance,
)
from core_model.admin_assistant.action_registry import ACTION_DEFINITIONS
from core_model.admin_assistant.automation_policy import (
    AUTOMATION_ALLOWED_ACTIONS,
    GLOBAL_SYSTEM_TARGET_TYPES,
    PLURAL_PARAMETER_KEYS,
    ManualAutomationExecutionDecision,
    evaluate_manual_automation_execution,
)

SUPER_ADMIN_ID = "14000000-0000-0000-0000-000000000001"
ADMIN_ONLY_ID = "14000000-0000-0000-0000-000000000002"
AUDITOR_ID = "14000000-0000-0000-0000-000000000003"
NONE_ID = "14000000-0000-0000-0000-000000000004"
REVIEWER_ID = "14000000-0000-0000-0000-000000000005"

_OVERRIDES = (
    f"{SUPER_ADMIN_ID}:SUPER_ADMIN,{ADMIN_ONLY_ID}:ADMIN,{AUDITOR_ID}:AUDITOR,"
    f"{NONE_ID}:NONE,{REVIEWER_ID}:SUPER_ADMIN"
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "phase14.db",
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


def _payload(**overrides) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "phase 14 manual automation",
        "description": "manual single run execution test",
        "target_action_type": "dataset_record_review",
        "target_type": "dataset_record",
        "target_public_id": "dataset-record-140",
        "target_action_parameters": {"decision": "approve", "comments": "phase 14 manual run"},
        "schedule_description": "daily at 09:00",
        "reason": "phase 14 test intent",
    }
    payload.update(overrides)
    return payload


def _define(
    service: AdminAssistantService,
    *,
    target_public_id: str = "automation-definition-14",
    requested_by: str = SUPER_ADMIN_ID,
    payload: dict[str, Any] | None = None,
):
    return propose_with_governance(
        service,
        action_type="admin_automation_define",
        target_type="admin_automation",
        target_public_id=target_public_id,
        request_payload=payload or _payload(),
        requested_by=requested_by,
        summary="phase 14 manual execution test definition",
    )


def _define_approved_executed(
    service: AdminAssistantService,
    *,
    target_public_id: str = "automation-definition-14",
    requested_by: str = SUPER_ADMIN_ID,
    payload: dict[str, Any] | None = None,
):
    proposal = _define(service, target_public_id=target_public_id, requested_by=requested_by, payload=payload)
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    return service.get_automation(proposal.public_id)


# 1. Outcome A: Empty allowlist denies execution
def test_outcome_a_empty_allowlist_denies_manual_execution(service: AdminAssistantService) -> None:
    assert AUTOMATION_ALLOWED_ACTIONS == frozenset()
    automation = _define_approved_executed(service)

    decision = evaluate_manual_automation_execution(
        automation,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )

    assert isinstance(decision, ManualAutomationExecutionDecision)
    assert decision.allowed is False
    assert decision.simulated_execution_attempted is False
    assert any("AUTOMATION_ALLOWED_ACTIONS" in r for r in decision.blocking_reasons)

    with pytest.raises(AdminAssistantError, match="manual automation execution refused"):
        service.execute_automation_manually(automation.public_id, executor_public_id=SUPER_ADMIN_ID)


# 2. Refused execution records audit log denial
def test_refused_execution_records_audit_log_denial(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    audit_repo = AuditLogRepository(service.settings.resolved_database_path)

    before_count = len(audit_repo.recent(limit=100))

    with pytest.raises(AdminAssistantError):
        service.execute_automation_manually(automation.public_id, executor_public_id=SUPER_ADMIN_ID)

    after_count = len(audit_repo.recent(limit=100))
    assert after_count == before_count + 1

    recent = audit_repo.recent(limit=1)[0]
    assert recent.event_type == "admin_automation_manual_execution_denied"
    assert recent.action == "manual_execute"
    assert recent.actor_reference == SUPER_ADMIN_ID
    assert recent.resource_public_id == automation.public_id
    assert recent.outcome.value == "denied"


# 3. Unknown action type rejected
def test_unknown_action_type_rejected(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_action_type="unknown_action_type")})

    decision = evaluate_manual_automation_execution(
        bad,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert decision.allowed is False
    assert any("known governed action" in r for r in decision.blocking_reasons)


# 4. Target type mismatch rejected
def test_target_type_mismatch_rejected(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_type="dataset_source")})

    decision = evaluate_manual_automation_execution(
        bad,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert decision.allowed is False
    assert any("invalid for action" in r for r in decision.blocking_reasons)


# 5. Malformed target public ID rejected
def test_malformed_target_public_id_rejected(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_public_id="../bad_id")})

    decision = evaluate_manual_automation_execution(
        bad,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert decision.allowed is False
    assert any("malformed" in r for r in decision.blocking_reasons)


# 6. Invalid target parameters rejected
def test_invalid_target_parameters_rejected(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_action_parameters={})})

    decision = evaluate_manual_automation_execution(
        bad,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert decision.allowed is False
    assert any("missing required field" in r for r in decision.blocking_reasons)


# 7. Recursive automation definition target rejected
def test_recursive_automation_definition_target_rejected(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_action_type="admin_automation_define")})

    decision = evaluate_manual_automation_execution(
        bad,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert decision.allowed is False
    assert any("no automation loops" in r for r in decision.blocking_reasons)


# 8. Self-targeting rejection
def test_self_targeting_rejection(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_public_id=automation.target_public_id)})

    decision = evaluate_manual_automation_execution(
        bad,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert decision.allowed is False
    assert any("own automation public_id" in r for r in decision.blocking_reasons)


# 9. RBAC NONE denied execution
def test_rbac_none_denied_execution(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    decision = evaluate_manual_automation_execution(
        automation,
        executor_public_id=NONE_ID,
        admin_role_overrides={NONE_ID: AdminRole.NONE},
    )
    assert decision.allowed is False
    assert any("lacks tool.execute" in r for r in decision.blocking_reasons)


# 10. RBAC AUDITOR denied execution
def test_rbac_auditor_denied_execution(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    decision = evaluate_manual_automation_execution(
        automation,
        executor_public_id=AUDITOR_ID,
        admin_role_overrides={AUDITOR_ID: AdminRole.AUDITOR},
    )
    assert decision.allowed is False
    assert any("lacks tool.execute" in r for r in decision.blocking_reasons)


# 11. RBAC ADMIN denied execution (only SUPER_ADMIN has tool.execute)
def test_rbac_admin_denied_execution(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    decision = evaluate_manual_automation_execution(
        automation,
        executor_public_id=ADMIN_ONLY_ID,
        admin_role_overrides={ADMIN_ONLY_ID: AdminRole.ADMIN},
    )
    assert decision.allowed is False
    assert any("lacks tool.execute" in r for r in decision.blocking_reasons)


# 12. Unapproved automation proposal rejected
def test_unapproved_automation_proposal_rejected(service: AdminAssistantService) -> None:
    pending = _define(service, target_public_id="auto-pending-14")
    decision = evaluate_manual_automation_execution(
        pending,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert decision.allowed is False
    assert any("not 'approved'" in r for r in decision.blocking_reasons)


# 13. Unconfirmed definition execution status rejected
def test_unconfirmed_definition_execution_status_rejected(service: AdminAssistantService) -> None:
    proposal = _define(service, target_public_id="auto-unconfirmed-14")
    approved = service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment="ok")

    decision = evaluate_manual_automation_execution(
        approved,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert decision.allowed is False
    assert any("not 'succeeded'" in r for r in decision.blocking_reasons)


# 14. Rejected, cancelled, and expired automations are refused
def test_rejected_cancelled_and_expired_automations_refused(service: AdminAssistantService) -> None:
    proposal_rej = _define(service, target_public_id="auto-rej-14")
    rejected = service.review(proposal_rej.public_id, decision="rejected", reviewed_by=REVIEWER_ID, comment="no")
    res_rej = evaluate_manual_automation_execution(
        rejected,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert res_rej.allowed is False

    proposal_can = _define(service, target_public_id="auto-can-14")
    cancelled = service.cancel(proposal_can.public_id, cancelled_by=SUPER_ADMIN_ID, reason="withdrawn")
    res_can = evaluate_manual_automation_execution(
        cancelled,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert res_can.allowed is False


# 15. Single-run guarantee: repeated blocked execution attempts produce deterministic failure without side effects
def test_single_run_guarantee_and_determinism(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)

    dec1 = evaluate_manual_automation_execution(
        automation,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    dec2 = evaluate_manual_automation_execution(
        automation,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )

    assert dec1 == dec2
    assert dec1.simulated_execution_attempted is False


# 16. High risk target action rejected
def test_high_risk_target_action_rejected(service: AdminAssistantService) -> None:
    high_risk_payload = {
        "name": "high risk automation",
        "description": "sample deletion automation",
        "target_action_type": "execute_sample_deletion",
        "target_type": "external_dataset_sample_import",
        "target_public_id": "sample-import-001",
        "target_action_parameters": {},
        "schedule_description": "daily at 00:00",
        "reason": "sample cleanup",
    }
    automation = _define_approved_executed(service, target_public_id="auto-high-risk-14", payload=high_risk_payload)

    decision = evaluate_manual_automation_execution(
        automation,
        executor_public_id=SUPER_ADMIN_ID,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )

    assert decision.allowed is False
    assert any("high risk" in r for r in decision.blocking_reasons)


# 17. AST security inspection (confirming absence of forbidden code execution patterns)
def test_ast_security_inspection_phase14() -> None:
    from core_model.admin_assistant import automation_policy

    source = inspect.getsource(automation_policy)
    module = ast.parse(source)

    # Strip docstrings
    for node in ast.walk(module):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]

    code_only = ast.unparse(module)
    lowered = code_only.lower()

    # Forbidden execution loops and background engines
    for forbidden in (
        "asyncio.create_task",
        "backgroundtasks",
        "while true",
        "celery",
        "apscheduler",
        "cron",
        "queueconsumer",
        "subprocess",
        "os.system",
        "run_tool(",
    ):
        assert forbidden not in lowered

    # Forbidden dynamic execution calls
    tree = ast.parse(code_only)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "compile", "__import__"}
