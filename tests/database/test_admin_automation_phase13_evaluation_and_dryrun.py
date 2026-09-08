"""Phase 13: Bounded Automation Evaluation, Dry-Run & Operator Observation.

Tests verify that the evaluation, simulation, and observation models are:
- Strictly read-only
- Deterministic
- Side-effect free
- Default-deny (AUTOMATION_ALLOWED_ACTIONS == frozenset())
- Never dispatch or execute the underlying ActionDefinition
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
from backend.services.admin_assistant_service import AdminAssistantService
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
    AutomationDryRunResult,
    AutomationEvaluationResult,
    AutomationObservation,
    dry_run_automation,
    evaluate_automation,
    observe_automation,
)

SUPER_ADMIN_ID = "13000000-0000-0000-0000-000000000001"
ADMIN_ONLY_ID = "13000000-0000-0000-0000-000000000002"
AUDITOR_ID = "13000000-0000-0000-0000-000000000003"
NONE_ID = "13000000-0000-0000-0000-000000000004"
REVIEWER_ID = "13000000-0000-0000-0000-000000000005"

_OVERRIDES = (
    f"{SUPER_ADMIN_ID}:SUPER_ADMIN,{AUDITOR_ID}:AUDITOR,"
    f"{NONE_ID}:NONE,{REVIEWER_ID}:SUPER_ADMIN"
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "phase13.db",
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
        "name": "phase 13 automation",
        "description": "bounded evaluation and dry run",
        "target_action_type": "dataset_record_review",
        "target_type": "dataset_record",
        "target_public_id": "dataset-record-001",
        "target_action_parameters": {"decision": "approve", "comments": "phase 13 review"},
        "schedule_description": "daily at 08:00",
        "reason": "phase 13 test intent",
    }
    payload.update(overrides)
    return payload


def _define(
    service: AdminAssistantService,
    *,
    target_public_id: str = "automation-definition-13",
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
        summary="phase 13 automation definition",
    )


def _define_approved_executed(
    service: AdminAssistantService,
    *,
    target_public_id: str = "automation-definition-13",
    requested_by: str = SUPER_ADMIN_ID,
    payload: dict[str, Any] | None = None,
):
    proposal = _define(service, target_public_id=target_public_id, requested_by=requested_by, payload=payload)
    service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment=None)
    execute_with_governance(service, proposal.public_id, executor_public_id=SUPER_ADMIN_ID)
    return service.get_automation(proposal.public_id)


# 1. Valid automation evaluation
def test_valid_automation_evaluation(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    result = evaluate_automation(
        automation,
        admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN},
    )
    assert isinstance(result, AutomationEvaluationResult)
    assert result.valid is True
    assert result.target_action_registered is True
    assert result.target_type_valid is True
    assert result.target_public_id_valid is True
    assert result.target_parameters_valid is True
    assert result.schedule_valid is True
    assert result.proposal_approved is True
    assert result.definition_executed is True
    assert result.defining_admin_rbac_permitted is True
    assert result.allowlist_allowed is False
    assert result.stale_fingerprint_available is True
    assert result.is_global_target is False
    assert any("AUTOMATION_ALLOWED_ACTIONS" in r for r in result.blocking_reasons)


# 2. Malformed target_type
def test_malformed_target_type(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_type="")})
    res = evaluate_automation(bad, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.target_type_valid is False
    assert any("target_type is required" in r for r in res.blocking_reasons)


# 3. Malformed target_public_id
def test_malformed_target_public_id(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_public_id="../escape")})
    res = evaluate_automation(bad, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.target_public_id_valid is False
    assert any("malformed" in r for r in res.blocking_reasons)


# 4. Unknown target action
def test_unknown_target_action(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_action_type="unknown_action_type")})
    res = evaluate_automation(bad, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.target_action_registered is False
    assert any("known governed action" in r for r in res.blocking_reasons)


# 5. Target type mismatch
def test_target_type_mismatch(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_type="dataset_source")})
    res = evaluate_automation(bad, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.target_type_valid is False
    assert any("invalid for action" in r for r in res.blocking_reasons)


# 6. Invalid target parameters
def test_invalid_target_parameters(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad_missing = automation.model_copy(update={"request_payload": _payload(target_action_parameters={})})
    res_missing = evaluate_automation(bad_missing, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res_missing.target_parameters_valid is False
    assert any("missing required field" in r for r in res_missing.blocking_reasons)

    bad_extra = automation.model_copy(
        update={"request_payload": _payload(target_action_parameters={"decision": "approve", "comments": "ok", "extra": 123})}
    )
    res_extra = evaluate_automation(bad_extra, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res_extra.target_parameters_valid is False
    assert any("unsupported field" in r for r in res_extra.blocking_reasons)


# 7. Recursive admin_automation_define target
def test_recursive_admin_automation_define_target(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_action_type="admin_automation_define")})
    res = evaluate_automation(bad, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert any("no automation loops" in r for r in res.blocking_reasons)


# 8. Self-targeting rejection
def test_self_targeting_rejection(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad = automation.model_copy(update={"request_payload": _payload(target_public_id=automation.target_public_id)})
    res = evaluate_automation(bad, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert any("own automation public_id" in r for r in res.blocking_reasons)


# 9. Empty allowlist denial
def test_empty_allowlist_denial(service: AdminAssistantService) -> None:
    assert AUTOMATION_ALLOWED_ACTIONS == frozenset()
    automation = _define_approved_executed(service)
    res = evaluate_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.allowlist_allowed is False
    assert any("AUTOMATION_ALLOWED_ACTIONS" in r for r in res.blocking_reasons)


# 10. Failed approval state
def test_failed_approval_state(service: AdminAssistantService) -> None:
    pending = _define(service, target_public_id="auto-pending")
    res_pending = evaluate_automation(pending, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res_pending.proposal_approved is False
    assert any("not 'approved'" in r for r in res_pending.blocking_reasons)

    rejected = _define(service, target_public_id="auto-rejected")
    rejected = service.review(rejected.public_id, decision="rejected", reviewed_by=REVIEWER_ID, comment="denied")
    res_rejected = evaluate_automation(rejected, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res_rejected.proposal_approved is False
    assert any("rejected" in r for r in res_rejected.blocking_reasons)


# 11. Failed execution state
def test_failed_execution_state(service: AdminAssistantService) -> None:
    proposal = _define(service, target_public_id="auto-not-executed")
    approved = service.review(proposal.public_id, decision="approved", reviewed_by=REVIEWER_ID, comment="ok")
    res = evaluate_automation(approved, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.definition_executed is False
    assert any("not 'succeeded'" in r for r in res.blocking_reasons)


# 12. Stale/missing fingerprint
def test_stale_missing_fingerprint(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    # create a mock payload targeting an action type that has no fingerprint
    mock = automation.model_copy(
        update={
            "request_payload": _payload(
                target_action_type="admin_automation_define",
                target_type="admin_automation",
                target_action_parameters={
                    "name": "nested",
                    "description": "nested",
                    "target_action_type": "dataset_record_review",
                    "target_type": "dataset_record",
                    "target_public_id": "rec-1",
                    "target_action_parameters": {"decision": "approve", "comments": "ok"},
                    "schedule_description": "daily at 08:00",
                },
            )
        }
    )
    res = evaluate_automation(mock, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.stale_fingerprint_available is False


# 13. Invalid schedule
def test_invalid_schedule(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    bad_interval = automation.model_copy(
        update={"request_payload": _payload(schedule={"kind": "interval", "interval_seconds": 60})}
    )
    res = evaluate_automation(bad_interval, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.schedule_valid is False
    assert any("sub-minimum" in r for r in res.blocking_reasons)


# 14. Valid schedule
def test_valid_schedule(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    valid_struct = automation.model_copy(
        update={"request_payload": _payload(schedule={"kind": "interval", "interval_seconds": 3600})}
    )
    res = evaluate_automation(valid_struct, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.schedule_valid is True


# 15. RBAC NONE
def test_rbac_none(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    res = evaluate_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.NONE})
    assert res.defining_admin_rbac_permitted is False
    assert any("lacks tool.execute" in r for r in res.blocking_reasons)


# 16. RBAC ADMIN
def test_rbac_admin(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    res = evaluate_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.ADMIN})
    # ADMIN role does not have TOOL_EXECUTE permission (only SUPER_ADMIN has TOOL_EXECUTE)
    assert res.defining_admin_rbac_permitted is False
    assert any("lacks tool.execute" in r for r in res.blocking_reasons)


# 17. RBAC SUPER_ADMIN
def test_rbac_super_admin(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    res = evaluate_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.defining_admin_rbac_permitted is True


# 18. Dry-run never executes target action & simulation status
def test_dry_run_never_executes_target_action(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    dry_run = dry_run_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})

    assert isinstance(dry_run, AutomationDryRunResult)
    assert dry_run.simulated_execution_attempted is False
    assert dry_run.simulation_status == "simulated_eligible_if_policy_allowed"
    assert "NO REAL ACTION WAS EXECUTED" in dry_run.message
    assert dry_run.target_action_type == "dataset_record_review"
    assert dry_run.target_type == "dataset_record"
    assert dry_run.target_public_id == "dataset-record-001"
    assert dry_run.evidence["requested_by"] == SUPER_ADMIN_ID
    assert dry_run.evidence["resolved_role"] == "super_admin"


# 19. Dry-run never writes database state
def test_dry_run_never_writes_database_state(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    audit_repo = AuditLogRepository(service.settings.resolved_database_path)

    before_audits = len(audit_repo.recent(limit=100))
    before_automation = service.get_automation(automation.public_id)

    dry_run = dry_run_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    observation = observe_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})

    after_audits = len(audit_repo.recent(limit=100))
    after_automation = service.get_automation(automation.public_id)

    assert before_audits == after_audits
    assert before_automation == after_automation
    assert dry_run.simulated_execution_attempted is False
    assert observation.is_blocked is True


# 20. Repeated evaluation remains read-only and deterministic
def test_repeated_evaluation_deterministic(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    res1 = evaluate_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    res2 = evaluate_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res1 == res2

    obs1 = observe_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    obs2 = observe_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert obs1 == obs2


# 21. Global target handling
def test_global_target_handling(service: AdminAssistantService) -> None:
    payload = {
        "name": "global backup check",
        "description": "evaluate global target",
        "target_action_type": "run_production_backup_readiness_check",
        "target_type": "production_readiness_system",
        "target_public_id": "production-readiness-system",
        "target_action_parameters": {},
        "schedule_description": "daily at 00:00",
        "reason": "backup verification",
    }
    automation = _define_approved_executed(service, target_public_id="auto-global-target", payload=payload)
    res = evaluate_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})

    assert res.is_global_target is True
    assert res.target_type in GLOBAL_SYSTEM_TARGET_TYPES
    assert any("global system singleton" in w for w in res.warnings)


# 22. Plural target parameter handling
def test_plural_target_parameter_handling(service: AdminAssistantService) -> None:
    payload = {
        "name": "plural gap merge",
        "description": "evaluate plural parameters",
        "target_action_type": "propose_duplicate_gap_merge",
        "target_type": "knowledge_gap_case",
        "target_public_id": "gap-case-001",
        "target_action_parameters": {
            "case_public_ids": ["gap-1", "gap-2"],
            "canonical_question": "question?",
            "primary_language": "ta",
        },
        "schedule_description": "interval 7200s",
        "reason": "gap merge",
    }
    automation = _define_approved_executed(service, target_public_id="auto-plural-target", payload=payload)
    res = evaluate_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})

    assert "case_public_ids" in res.plural_parameters
    assert any("plural parameter collections" in w for w in res.warnings)


# 23. Operator observation diagnostic model
def test_operator_observation_model(service: AdminAssistantService) -> None:
    automation = _define_approved_executed(service)
    obs = observe_automation(automation, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})

    assert isinstance(obs, AutomationObservation)
    assert obs.automation_public_id == automation.public_id
    assert obs.name == "phase 13 automation"
    assert obs.target_action_type == "dataset_record_review"
    assert obs.target_type == "dataset_record"
    assert obs.target_public_id == "dataset-record-001"
    assert obs.is_blocked is True
    assert obs.future_eligibility == "eligible_pending_policy_allowlist"
    assert obs.governance_checks["proposal_approved"] is True
    assert obs.governance_checks["definition_executed"] is True
    assert obs.governance_checks["defining_admin_rbac_permitted"] is True
    assert obs.governance_checks["allowlist_allowed"] is False
    assert obs.validation_checks["target_definition_valid"] is True


# 24. Non-automation approval rejected
def test_non_automation_approval_rejected(service: AdminAssistantService) -> None:
    proposal = propose_with_governance(
        service,
        action_type="dataset_source_update",
        target_type="dataset_source",
        target_public_id="source-1",
        request_payload={"name": "test", "source_type": "web", "url": "https://example.com", "license": "MIT", "notes": ""},
        requested_by=SUPER_ADMIN_ID,
        summary="not an automation",
    )
    res = evaluate_automation(proposal, admin_role_overrides={SUPER_ADMIN_ID: AdminRole.SUPER_ADMIN})
    assert res.valid is False
    assert res.blocking_reasons == ("not an admin_automation definition",)


# 25. AST security inspection
def test_ast_security_inspection() -> None:
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
        "execute_with_governance(",
    ):
        assert forbidden not in lowered

    # Forbidden dynamic execution calls
    tree = ast.parse(code_only)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "compile", "__import__"}
