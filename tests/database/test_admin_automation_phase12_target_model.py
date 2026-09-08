"""Phase 12: automation target model and safe-action eligibility.

This suite intentionally proves only the control plane. It does not add
or exercise any scheduler, worker, queue, polling loop, or autonomous
execution path.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.phase2 import AuditLogRepository
from backend.models.domain import ApprovalStatus, ExecutionStatus
from backend.services.admin_assistant_service import AdminAssistantService
from backend.services.admin_assistant_tool_governance import AdminRole, ToolAuthorizationError
from backend.services.admin_assistant_write_governance import (
    execute_with_governance,
    propose_with_governance,
)
from core_model.admin_assistant.action_registry import ACTION_DEFINITIONS
from core_model.admin_assistant.automation_policy import (
    AUTOMATION_ALLOWED_ACTIONS,
    evaluate_automation_execution_readiness,
    validate_automation_target_definition,
)

SUPER_ADMIN_ID = "12000000-0000-0000-0000-000000000001"
ADMIN_ONLY_ID = "12000000-0000-0000-0000-000000000002"
AUDITOR_ID = "12000000-0000-0000-0000-000000000003"
NONE_ID = "12000000-0000-0000-0000-000000000004"
REVIEWER_ID = "12000000-0000-0000-0000-000000000005"

_OVERRIDES = (
    f"{SUPER_ADMIN_ID}:SUPER_ADMIN,{AUDITOR_ID}:AUDITOR,"
    f"{NONE_ID}:NONE,{REVIEWER_ID}:SUPER_ADMIN"
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "phase12.db",
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


def _payload(**overrides) -> dict:
    payload = {
        "name": "targeted automation",
        "description": "phase 12 validation",
        "target_action_type": "dataset_record_review",
        "target_type": "dataset_record",
        "target_public_id": "dataset-record-target",
        "target_action_parameters": {"decision": "approve", "comments": "phase 12"},
        "schedule_description": "daily at 09:00",
        "reason": "phase 12 test",
    }
    payload.update(overrides)
    return payload


def _define(
    service: AdminAssistantService,
    *,
    target_public_id: str = "automation-definition",
    requested_by: str = SUPER_ADMIN_ID,
    payload: dict | None = None,
):
    return propose_with_governance(
        service,
        action_type="admin_automation_define",
        target_type="admin_automation",
        target_public_id=target_public_id,
        request_payload=payload or _payload(),
        requested_by=requested_by,
        summary="phase 12 automation",
    )


def _define_approved_executed(service: AdminAssistantService):
    proposal = _define(service)
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    return service.get_automation(proposal.public_id)


def test_target_model_validation_accepts_explicit_action_target() -> None:
    result = validate_automation_target_definition(_payload())
    assert result.valid is True
    assert result.errors == ()


@pytest.mark.parametrize(
    "overrides,expected",
    [
        ({"target_action_type": "missing_action"}, "known governed action"),
        ({"target_type": "dataset_source"}, "invalid for action"),
        ({"target_public_id": ""}, "target_public_id is required"),
        ({"target_public_id": "../bad"}, "malformed"),
        ({"target_action_parameters": {}}, "missing required field"),
        (
            {
                "target_action_parameters": {
                    "decision": "approve",
                    "comments": "ok",
                    "ignored": True,
                }
            },
            "unsupported field",
        ),
    ],
)
def test_target_model_validation_rejects_invalid_shapes(overrides: dict, expected: str) -> None:
    result = validate_automation_target_definition(_payload(**overrides))
    assert result.valid is False
    assert any(expected in error for error in result.errors)


def test_recursive_and_self_targeting_definitions_fail_closed() -> None:
    recursive = validate_automation_target_definition(
        _payload(target_action_type="admin_automation_define")
    )
    assert recursive.valid is False
    assert any("no automation loops" in error for error in recursive.errors)

    self_target = validate_automation_target_definition(
        _payload(target_public_id="automation-definition"),
        automation_public_id="automation-definition",
    )
    assert self_target.valid is False
    assert any("own automation public_id" in error for error in self_target.errors)


def test_admin_automation_define_requires_underlying_target(service: AdminAssistantService) -> None:
    proposal = _define(service, payload=_payload(target_type=None))
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    with pytest.raises(Exception, match="target_type is required"):
        execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)


def test_allowlist_remains_empty_after_action_eligibility_audit() -> None:
    assert AUTOMATION_ALLOWED_ACTIONS == frozenset()
    known = {definition.action_type for definition in ACTION_DEFINITIONS}
    assert "test_external_data_provider_connection" in known
    assert "dataset_record_review" in known
    assert "execute_sample_deletion" in known
    assert not AUTOMATION_ALLOWED_ACTIONS & known


def test_readiness_distinguishes_missing_invalid_unknown_and_not_allowlisted(
    service: AdminAssistantService,
) -> None:
    automation = _define_approved_executed(service)
    decision = evaluate_automation_execution_readiness(
        automation,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert decision.ready is False
    assert any("AUTOMATION_ALLOWED_ACTIONS" in reason for reason in decision.blocking_reasons)

    missing = automation.model_copy(update={"request_payload": _payload(target_public_id=None)})
    missing_decision = evaluate_automation_execution_readiness(
        missing,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert any("target_public_id is required" in r for r in missing_decision.blocking_reasons)

    invalid = automation.model_copy(update={"request_payload": _payload(target_type="dataset_source")})
    invalid_decision = evaluate_automation_execution_readiness(
        invalid,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert any("invalid for action" in r for r in invalid_decision.blocking_reasons)

    unknown = automation.model_copy(
        update={"request_payload": _payload(target_action_type="not_a_real_action")}
    )
    unknown_decision = evaluate_automation_execution_readiness(
        unknown,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert any("known governed action" in r for r in unknown_decision.blocking_reasons)


def test_readiness_distinguishes_governance_lifecycle_states(service: AdminAssistantService) -> None:
    pending = _define(service, target_public_id="automation-pending")
    pending_decision = evaluate_automation_execution_readiness(pending, admin_role_overrides={})
    assert any("not 'approved'" in reason for reason in pending_decision.blocking_reasons)

    rejected = _define(service, target_public_id="automation-rejected")
    rejected = service.review(
        rejected.public_id,
        decision="rejected",
        reviewed_by=REVIEWER_ID,
        comment="no",
    )
    rejected_decision = evaluate_automation_execution_readiness(rejected, admin_role_overrides={})
    assert any("rejected" in reason for reason in rejected_decision.blocking_reasons)

    executed = _define_approved_executed(service)
    succeeded_again = evaluate_automation_execution_readiness(executed, admin_role_overrides={})
    assert any("AUTOMATION_ALLOWED_ACTIONS" in reason for reason in succeeded_again.blocking_reasons)

    already_executed = executed.model_copy(update={"execution_status": ExecutionStatus.FAILED})
    already_decision = evaluate_automation_execution_readiness(
        already_executed,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert any("not 'succeeded'" in reason for reason in already_decision.blocking_reasons)

    expired = executed.model_copy(update={"status": ApprovalStatus.EXPIRED})
    expired_decision = evaluate_automation_execution_readiness(expired, admin_role_overrides={})
    assert any("expired" in reason for reason in expired_decision.blocking_reasons)


def test_rbac_and_governance_flow_remain_compatible(service: AdminAssistantService) -> None:
    with pytest.raises(ToolAuthorizationError):
        _define(service, target_public_id="none-denied", requested_by=NONE_ID)
    with pytest.raises(ToolAuthorizationError):
        _define(service, target_public_id="auditor-denied", requested_by=AUDITOR_ID)

    admin_proposal = _define(
        service,
        target_public_id="admin-can-propose",
        requested_by=ADMIN_ONLY_ID,
    )
    service.review(
        admin_proposal.public_id,
        decision="approved",
        reviewed_by=REVIEWER_ID,
        comment=None,
    )
    with pytest.raises(ToolAuthorizationError):
        execute_with_governance(
            service,
            admin_proposal.public_id,
            executor_public_id=ADMIN_ONLY_ID,
        )


def test_duplicate_execution_and_readiness_mutation_safety(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    with pytest.raises(Exception, match="not awaiting execution"):
        execute_with_governance(service, automation.public_id, executor_public_id=SUPER_ADMIN_ID)

    before = service.get_automation(automation.public_id)
    audit_before = len(AuditLogRepository(service.settings.resolved_database_path).recent(limit=100))
    evaluate_automation_execution_readiness(
        before,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    after = service.get_automation(automation.public_id)
    audit_after = len(AuditLogRepository(service.settings.resolved_database_path).recent(limit=100))
    assert before == after
    assert audit_before == audit_after


def test_no_execution_engine_or_arbitrary_code_surface_was_added() -> None:
    from core_model.admin_assistant import automation_policy

    source = inspect.getsource(automation_policy)
    module = ast.parse(source)
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
    for forbidden in (
        "asyncio.create_task",
        "backgroundtasks",
        "while true",
        "celery",
        "apscheduler",
        "cron",
        "queueconsumer",
    ):
        assert forbidden not in lowered

    tree = ast.parse(code_only)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "compile", "__import__"}
    assert "subprocess" not in lowered
