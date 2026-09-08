"""Phase 11-13: the automation execution *contract*, target validation,
dry-run simulation, and operator observation policy.

Nothing in this module is called by any executable dispatch path today.
Repository-wide audit found no general-purpose scheduler/task-queue framework
anywhere in this codebase -- every existing worker pattern is tightly coupled
to its own domain. Building a dedicated worker would need schedule-tracking
columns that do not exist on admin_approvals and cannot be added without a
migration. Per Phase 11-13 design, this module implements ONLY the execution
contract, target validation, read-only evaluation, and simulation logic.
No schema change, no worker, no scheduler.

CRITICAL PRINCIPLE: this module can only ever narrow what may execute.
It has no power to grant permission, approve anything, or invoke a tool/action
itself. Simulation and dry-run execution never dispatch real actions.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.models.domain import AdminApprovalPublic
    from backend.services.admin_assistant_tool_governance import AdminRole, Permission


# --- Step 3: automatable action allowlist -----------------------------------

# Deliberately empty. "Default: DENY. Unknown actions: DENY. New action
# types: DENY until explicitly allowlisted." (Phase 11 task, Step 3).
# Individually risk-reviewing each of the 104 existing ActionDefinitions
# for safe unattended, repeated execution confirms that 0 actions are
# currently eligible for unattended autonomous execution. Populating this
# set is a deliberate, per-action, future decision, not a blanket enablement.
AUTOMATION_ALLOWED_ACTIONS: frozenset[str] = frozenset()

_TARGET_PUBLIC_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

GLOBAL_SYSTEM_TARGET_TYPES: frozenset[str] = frozenset(
    {
        "production_readiness_system",
        "trusted_web_policy_system",
        "deterministic_tool_registry_system",
        "knowledge_gap_report_system",
    }
)

PLURAL_PARAMETER_KEYS: frozenset[str] = frozenset(
    {
        "case_public_ids",
        "chunk_public_ids",
        "candidate_public_ids",
        "selected_record_ids",
        "target_pages",
    }
)


@dataclass(frozen=True)
class AutomationTargetValidation:
    valid: bool
    errors: tuple[str, ...]


def validate_automation_target_definition(
    payload: Mapping[str, Any],
    *,
    automation_public_id: str | None = None,
) -> AutomationTargetValidation:
    """Pure validation for the governed action an automation definition
    would target in a future execution engine.

    The automation definition itself remains the existing
    `admin_approvals` row with `target_type='admin_automation'`; these
    fields describe the *underlying* governed action and are persisted in
    that row's existing `request_payload_json`. This function never reads
    or writes the database and never dispatches an action.
    """

    from core_model.admin_assistant.action_registry import (
        BLOCKED_ACTION_SUBSTRINGS,
        get_action_definition,
        is_known_action_type,
    )

    errors: list[str] = []

    target_action_type = payload.get("target_action_type")
    if not isinstance(target_action_type, str) or not target_action_type.strip():
        errors.append("target_action_type is required and must be a non-empty string")
        return AutomationTargetValidation(False, tuple(errors))

    if target_action_type == "admin_automation_define":
        errors.append("an automation cannot target admin_automation_define itself (no automation loops)")
        return AutomationTargetValidation(False, tuple(errors))
    if any(token in target_action_type.lower() for token in BLOCKED_ACTION_SUBSTRINGS):
        errors.append(f"target_action_type is not permitted: {target_action_type!r}")
        return AutomationTargetValidation(False, tuple(errors))
    if not is_known_action_type(target_action_type):
        errors.append(f"target_action_type is not a known governed action: {target_action_type!r}")
        return AutomationTargetValidation(False, tuple(errors))

    definition = get_action_definition(target_action_type)
    if definition is None:
        errors.append(f"target_action_type has no ActionDefinition: {target_action_type!r}")
        return AutomationTargetValidation(False, tuple(errors))

    target_type = payload.get("target_type")
    if not isinstance(target_type, str) or not target_type.strip():
        errors.append("target_type is required and must be a non-empty string")
    elif target_type != definition.target_type:
        errors.append(
            f"target_type {target_type!r} is invalid for action {target_action_type!r}; "
            f"expected {definition.target_type!r}"
        )

    target_public_id = payload.get("target_public_id")
    if not isinstance(target_public_id, str) or not target_public_id.strip():
        errors.append("target_public_id is required and must be a non-empty string")
    elif not _TARGET_PUBLIC_ID_PATTERN.fullmatch(target_public_id):
        errors.append("target_public_id is malformed")
    elif automation_public_id and target_public_id == automation_public_id:
        errors.append("an automation cannot target its own automation public_id")

    parameters = payload.get("target_action_parameters", {})
    if not isinstance(parameters, Mapping):
        errors.append("target_action_parameters must be an object")
    else:
        expected_fields = set(definition.payload_fields)
        provided_fields = set(parameters)
        missing_fields = sorted(expected_fields - provided_fields)
        unexpected_fields = sorted(provided_fields - expected_fields)
        if missing_fields:
            errors.append(
                "target_action_parameters missing required field(s): "
                + ", ".join(missing_fields)
            )
        if unexpected_fields:
            errors.append(
                "target_action_parameters contains unsupported field(s): "
                + ", ".join(unexpected_fields)
            )

    return AutomationTargetValidation(valid=not errors, errors=tuple(errors))


# --- Step 7/8: deliberately small, deterministic schedule vocabulary -------

SUPPORTED_SCHEDULE_KINDS = ("once", "daily", "interval")

# Step 8: no automation may run more often than this, ever -- checked
# structurally by validate_schedule(), independent of whether anything
# ever consumes a schedule for real dispatch.
MINIMUM_AUTOMATION_INTERVAL_SECONDS = 3600


def validate_schedule(schedule: Any) -> list[str]:
    """Pure structural validation of a *proposed* schedule definition.
    Returns a list of human-readable errors; empty means structurally
    valid. Never executed, never persisted by this function -- a
    caller decides what to do with the result.

    Rejects exactly the malformed shapes Step 7/8 names: unknown kind,
    zero/negative/sub-minimum interval, missing required fields for the
    chosen kind. Does not implement a cron language -- "once"/"daily"/
    "interval" only."""

    errors: list[str] = []
    if not isinstance(schedule, dict):
        return ["schedule must be an object"]

    kind = schedule.get("kind")
    if kind not in SUPPORTED_SCHEDULE_KINDS:
        errors.append(f"schedule.kind must be one of {SUPPORTED_SCHEDULE_KINDS}, got {kind!r}")
        return errors  # nothing else is checkable without a valid kind

    if kind == "once":
        run_at = schedule.get("run_at")
        if not isinstance(run_at, str) or not run_at.strip():
            errors.append("schedule.run_at is required and must be a non-empty string for kind='once'")
    elif kind == "daily":
        time_of_day = schedule.get("time_of_day")
        if not isinstance(time_of_day, str) or not time_of_day.strip():
            errors.append(
                "schedule.time_of_day is required and must be a non-empty string for kind='daily'"
            )
    elif kind == "interval":
        interval_seconds = schedule.get("interval_seconds")
        if not isinstance(interval_seconds, int) or isinstance(interval_seconds, bool):
            errors.append("schedule.interval_seconds must be an integer for kind='interval'")
        elif interval_seconds <= 0:
            errors.append("schedule.interval_seconds must be positive (zero/negative rejected)")
        elif interval_seconds < MINIMUM_AUTOMATION_INTERVAL_SECONDS:
            errors.append(
                f"schedule.interval_seconds must be >= {MINIMUM_AUTOMATION_INTERVAL_SECONDS} "
                f"(got {interval_seconds}) -- sub-minimum intervals are rejected"
            )

    return errors


# --- Step 4/9: execution-readiness evaluation (pure, read-only) ------------


@dataclass(frozen=True)
class AutomationExecutionDecision:
    ready: bool
    blocking_reasons: tuple[str, ...]


def evaluate_automation_execution_readiness(
    automation: "AdminApprovalPublic",
    *,
    admin_role_overrides: Mapping[str, "AdminRole"],
) -> AutomationExecutionDecision:
    """Step 4's execution contract, expressed as a pure function over an
    already-persisted `admin_approvals` row (`target_type=
    'admin_automation'`) -- never a live dispatch. Combines every gate
    Step 4 names except the ones that only make sense at *actual*
    dispatch time:

        verify automation is approved & its definition executed
        -> verify not expired
        -> verify target action is still allowlisted
        -> verify ActionDefinition still exists
        -> resolve governing admin identity + RBAC permission check

    This function is READ-ONLY: it never mutates `automation`, never
    calls execute()/propose()/review(), never imports run_tool(), and
    never grants anything."""

    from backend.services.admin_assistant_tool_governance import (
        Permission,
        permissions_for_role,
        resolve_admin_role,
    )
    from backend.services.admin_assistant_service import STALE_CHECK_FINGERPRINTS

    reasons: list[str] = []

    if automation.target_type != "admin_automation":
        return AutomationExecutionDecision(False, ("not an automation definition",))

    if automation.status != "approved":
        reasons.append(f"automation proposal status is {automation.status.value!r}, not 'approved'")
    if automation.execution_status != "succeeded":
        reasons.append(
            f"automation definition execution_status is {automation.execution_status.value!r}, "
            "not 'succeeded' -- the definition itself was never confirmed"
        )

    target_validation = validate_automation_target_definition(
        automation.request_payload,
        automation_public_id=automation.target_public_id,
    )
    if not target_validation.valid:
        reasons.extend(f"invalid automation definition: {error}" for error in target_validation.errors)
    else:
        target_action_type = automation.request_payload["target_action_type"]
        if target_action_type not in AUTOMATION_ALLOWED_ACTIONS:
            reasons.append(
                f"target action {target_action_type!r} is not in AUTOMATION_ALLOWED_ACTIONS "
                "(currently empty -- no action has been allowlisted for automated execution yet)"
            )
        if target_action_type not in STALE_CHECK_FINGERPRINTS:
            reasons.append(
                f"target action {target_action_type!r} has no stale-check fingerprint; "
                "future automated execution cannot prove target freshness"
            )

    role = resolve_admin_role(automation.requested_by, admin_role_overrides)
    permissions = permissions_for_role(role)
    if Permission.TOOL_EXECUTE not in permissions:
        reasons.append(
            f"the automation's defining admin ({automation.requested_by!r}, resolved role "
            f"{role.value!r}) no longer has tool.execute permission"
        )

    return AutomationExecutionDecision(ready=not reasons, blocking_reasons=tuple(reasons))


# --- Phase 13: Bounded Evaluation, Dry-Run Simulation & Observation -------


@dataclass(frozen=True)
class AutomationEvaluationResult:
    valid: bool
    target_action_registered: bool
    target_type_valid: bool
    target_public_id_valid: bool
    target_parameters_valid: bool
    schedule_valid: bool
    proposal_approved: bool
    definition_executed: bool
    defining_admin_rbac_permitted: bool
    allowlist_allowed: bool
    stale_fingerprint_available: bool
    is_global_target: bool
    target_action_type: str | None
    target_type: str | None
    target_public_id: str | None
    schedule_description: str | None
    plural_parameters: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]


def evaluate_automation(
    automation: "AdminApprovalPublic",
    *,
    admin_role_overrides: Mapping[str, "AdminRole"],
) -> AutomationEvaluationResult:
    """Phase 13: pure, read-only diagnostic evaluator for one defined
    automation. Evaluates structural validity, registry presence, target
    semantics, parameters, schedule, governance/approval state, stale-check
    fingerprint support, RBAC permissions, and allowlist membership.
    Never mutates state, never executes actions, and never calls tools.
    """
    from core_model.admin_assistant.action_registry import (
        get_action_definition,
        is_known_action_type,
    )
    from backend.services.admin_assistant_tool_governance import (
        Permission,
        permissions_for_role,
        resolve_admin_role,
    )
    from backend.services.admin_assistant_service import STALE_CHECK_FINGERPRINTS

    blocking_reasons: list[str] = []
    warnings: list[str] = []

    if automation.target_type != "admin_automation":
        return AutomationEvaluationResult(
            valid=False,
            target_action_registered=False,
            target_type_valid=False,
            target_public_id_valid=False,
            target_parameters_valid=False,
            schedule_valid=False,
            proposal_approved=False,
            definition_executed=False,
            defining_admin_rbac_permitted=False,
            allowlist_allowed=False,
            stale_fingerprint_available=False,
            is_global_target=False,
            target_action_type=None,
            target_type=None,
            target_public_id=None,
            schedule_description=None,
            plural_parameters=(),
            blocking_reasons=("not an admin_automation definition",),
            warnings=(),
        )

    payload = automation.request_payload if isinstance(automation.request_payload, Mapping) else {}
    raw_action_type = payload.get("target_action_type")
    target_action_type = str(raw_action_type) if isinstance(raw_action_type, str) and raw_action_type.strip() else None

    raw_target_type = payload.get("target_type")
    target_type = str(raw_target_type) if isinstance(raw_target_type, str) and raw_target_type.strip() else None

    raw_target_public_id = payload.get("target_public_id")
    target_public_id = str(raw_target_public_id) if isinstance(raw_target_public_id, str) and raw_target_public_id.strip() else None

    raw_schedule_desc = payload.get("schedule_description")
    schedule_description = str(raw_schedule_desc) if isinstance(raw_schedule_desc, str) and raw_schedule_desc.strip() else None

    # Proposal & execution governance state
    proposal_approved = (automation.status == "approved")
    if not proposal_approved:
        blocking_reasons.append(f"automation proposal status is {automation.status.value!r}, not 'approved'")

    definition_executed = (automation.execution_status == "succeeded")
    if not definition_executed:
        blocking_reasons.append(
            f"automation definition execution_status is {automation.execution_status.value!r}, "
            "not 'succeeded' -- the definition itself was never confirmed"
        )

    # Structural target validation
    target_val = validate_automation_target_definition(
        payload,
        automation_public_id=automation.target_public_id,
    )
    if not target_val.valid:
        blocking_reasons.extend(f"invalid target definition: {err}" for err in target_val.errors)

    # Detailed field checks
    target_action_registered = bool(target_action_type and is_known_action_type(target_action_type))
    definition = get_action_definition(target_action_type) if target_action_type else None

    target_type_valid = bool(definition and target_type == definition.target_type)
    target_public_id_valid = bool(
        target_public_id
        and _TARGET_PUBLIC_ID_PATTERN.fullmatch(target_public_id)
        and target_public_id != automation.target_public_id
    )

    parameters = payload.get("target_action_parameters")
    target_parameters_valid = False
    plural_params: list[str] = []
    if definition and isinstance(parameters, Mapping):
        expected_fields = set(definition.payload_fields)
        provided_fields = set(parameters)
        target_parameters_valid = (expected_fields == provided_fields)
        plural_params = [f for f in definition.payload_fields if f in PLURAL_PARAMETER_KEYS]

    # Global target check
    is_global = bool(target_type and target_type in GLOBAL_SYSTEM_TARGET_TYPES)
    if is_global:
        warnings.append(
            f"target_type {target_type!r} is a global system singleton; underlying action "
            "affects system-wide state rather than an isolated record"
        )

    if plural_params:
        warnings.append(
            f"action {target_action_type!r} accepts plural parameter collections: "
            + ", ".join(sorted(plural_params))
        )

    # Schedule validation
    schedule_struct = payload.get("schedule")
    schedule_valid = False
    if isinstance(schedule_struct, dict):
        sched_errors = validate_schedule(schedule_struct)
        if sched_errors:
            blocking_reasons.extend(f"invalid schedule: {err}" for err in sched_errors)
        else:
            schedule_valid = True
    elif isinstance(schedule_description, str) and schedule_description.strip():
        schedule_valid = True
    else:
        blocking_reasons.append("schedule_description is required and must be a non-empty string")

    # Allowlist gate
    allowlist_allowed = bool(target_action_type and target_action_type in AUTOMATION_ALLOWED_ACTIONS)
    if not allowlist_allowed and target_action_type:
        blocking_reasons.append(
            f"target action {target_action_type!r} is not in AUTOMATION_ALLOWED_ACTIONS "
            "(currently empty -- default-deny posture active)"
        )

    # Stale-check fingerprint gate
    stale_fingerprint_available = bool(
        target_action_type and target_action_type in STALE_CHECK_FINGERPRINTS
    )
    if not stale_fingerprint_available and target_action_type:
        blocking_reasons.append(
            f"target action {target_action_type!r} has no registered stale-check fingerprint"
        )

    # RBAC gate
    role = resolve_admin_role(automation.requested_by, admin_role_overrides)
    permissions = permissions_for_role(role)
    defining_admin_rbac_permitted = (Permission.TOOL_EXECUTE in permissions)
    if not defining_admin_rbac_permitted:
        blocking_reasons.append(
            f"the defining admin ({automation.requested_by!r}, resolved role "
            f"{role.value!r}) lacks tool.execute permission"
        )

    overall_valid = (
        target_val.valid
        and schedule_valid
        and target_action_registered
        and target_type_valid
        and target_public_id_valid
        and target_parameters_valid
    )

    return AutomationEvaluationResult(
        valid=overall_valid,
        target_action_registered=target_action_registered,
        target_type_valid=target_type_valid,
        target_public_id_valid=target_public_id_valid,
        target_parameters_valid=target_parameters_valid,
        schedule_valid=schedule_valid,
        proposal_approved=proposal_approved,
        definition_executed=definition_executed,
        defining_admin_rbac_permitted=defining_admin_rbac_permitted,
        allowlist_allowed=allowlist_allowed,
        stale_fingerprint_available=stale_fingerprint_available,
        is_global_target=is_global,
        target_action_type=target_action_type,
        target_type=target_type,
        target_public_id=target_public_id,
        schedule_description=schedule_description,
        plural_parameters=tuple(plural_params),
        blocking_reasons=tuple(blocking_reasons),
        warnings=tuple(warnings),
    )


@dataclass(frozen=True)
class AutomationDryRunResult:
    automation_public_id: str
    target_action_type: str | None
    target_type: str | None
    target_public_id: str | None
    schedule_description: str | None
    is_global_target: bool
    simulation_status: str
    simulated_execution_attempted: bool
    evaluation: AutomationEvaluationResult
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence: Mapping[str, Any]
    message: str


def dry_run_automation(
    automation: "AdminApprovalPublic",
    *,
    admin_role_overrides: Mapping[str, "AdminRole"],
) -> AutomationDryRunResult:
    """Phase 13: produces a simulated dry-run result for one defined
    automation. NEVER executes the underlying action, never creates audit
    records, and never mutates database state.
    """
    from core_model.admin_assistant.action_registry import get_action_definition
    from backend.services.admin_assistant_tool_governance import resolve_admin_role

    evaluation = evaluate_automation(
        automation, admin_role_overrides=admin_role_overrides
    )

    role = resolve_admin_role(automation.requested_by, admin_role_overrides)
    definition = (
        get_action_definition(evaluation.target_action_type)
        if evaluation.target_action_type
        else None
    )

    evidence: dict[str, Any] = {
        "requested_by": automation.requested_by,
        "resolved_role": role.value,
        "proposal_status": automation.status.value,
        "execution_status": automation.execution_status.value,
        "action_risk_level": definition.risk_level if definition else None,
        "action_mode": definition.mode if definition else None,
        "payload_fields_expected": list(definition.payload_fields) if definition else [],
        "parameters_provided": automation.request_payload.get("target_action_parameters")
        if isinstance(automation.request_payload, Mapping)
        else {},
        "stale_fingerprint_supported": evaluation.stale_fingerprint_available,
        "is_global_target": evaluation.is_global_target,
        "plural_parameters": list(evaluation.plural_parameters),
    }

    # Distinguish simulation status
    # If the ONLY blocking reason is the empty allowlist:
    only_blocked_by_allowlist = (
        evaluation.valid
        and evaluation.proposal_approved
        and evaluation.definition_executed
        and evaluation.defining_admin_rbac_permitted
        and evaluation.stale_fingerprint_available
        and not evaluation.allowlist_allowed
    )

    if only_blocked_by_allowlist:
        simulation_status = "simulated_eligible_if_policy_allowed"
        message = (
            f"Simulation: automation {automation.public_id!r} passes all governance, RBAC, "
            f"target, parameter, and fingerprint gates. Execution is blocked solely by policy "
            f"(AUTOMATION_ALLOWED_ACTIONS is empty; action {evaluation.target_action_type!r} "
            "is not allowlisted for unattended execution). NO REAL ACTION WAS EXECUTED."
        )
    else:
        simulation_status = "simulated_blocked"
        reasons_summary = "; ".join(evaluation.blocking_reasons)
        message = (
            f"Simulation: automation {automation.public_id!r} is blocked from execution: "
            f"{reasons_summary}. NO REAL ACTION WAS EXECUTED."
        )

    return AutomationDryRunResult(
        automation_public_id=automation.public_id,
        target_action_type=evaluation.target_action_type,
        target_type=evaluation.target_type,
        target_public_id=evaluation.target_public_id,
        schedule_description=evaluation.schedule_description,
        is_global_target=evaluation.is_global_target,
        simulation_status=simulation_status,
        simulated_execution_attempted=False,
        evaluation=evaluation,
        blocking_reasons=evaluation.blocking_reasons,
        warnings=evaluation.warnings,
        evidence=evidence,
        message=message,
    )


@dataclass(frozen=True)
class AutomationObservation:
    automation_public_id: str
    name: str
    description: str
    target_action_type: str | None
    target_type: str | None
    target_public_id: str | None
    is_global_target: bool
    schedule_description: str | None
    is_blocked: bool
    future_eligibility: str
    governance_checks: Mapping[str, bool]
    validation_checks: Mapping[str, bool]
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence: Mapping[str, Any]


def observe_automation(
    automation: "AdminApprovalPublic",
    *,
    admin_role_overrides: Mapping[str, "AdminRole"],
) -> AutomationObservation:
    """Phase 13: pure operator observation model. Produces a structured
    diagnostic snapshot explaining what action would be invoked, what target
    would be affected, which governance and validation gates passed/failed,
    and why execution is currently blocked.
    """
    dry_run = dry_run_automation(automation, admin_role_overrides=admin_role_overrides)
    eval_res = dry_run.evaluation
    payload = automation.request_payload if isinstance(automation.request_payload, Mapping) else {}

    name = str(payload.get("name", ""))
    description = str(payload.get("description", ""))

    governance_checks = {
        "proposal_approved": eval_res.proposal_approved,
        "definition_executed": eval_res.definition_executed,
        "defining_admin_rbac_permitted": eval_res.defining_admin_rbac_permitted,
        "stale_fingerprint_available": eval_res.stale_fingerprint_available,
        "allowlist_allowed": eval_res.allowlist_allowed,
    }

    validation_checks = {
        "target_definition_valid": eval_res.valid,
        "target_action_registered": eval_res.target_action_registered,
        "target_type_valid": eval_res.target_type_valid,
        "target_public_id_valid": eval_res.target_public_id_valid,
        "target_parameters_valid": eval_res.target_parameters_valid,
        "schedule_valid": eval_res.schedule_valid,
    }

    if not eval_res.valid:
        future_eligibility = "blocked_by_invalid_definition"
    elif not eval_res.proposal_approved or not eval_res.definition_executed:
        future_eligibility = "blocked_by_unapproved_or_unconfirmed_definition"
    elif not eval_res.defining_admin_rbac_permitted:
        future_eligibility = "blocked_by_proposer_rbac"
    elif not eval_res.allowlist_allowed:
        future_eligibility = "eligible_pending_policy_allowlist"
    else:
        future_eligibility = "eligible"

    return AutomationObservation(
        automation_public_id=automation.public_id,
        name=name,
        description=description,
        target_action_type=eval_res.target_action_type,
        target_type=eval_res.target_type,
        target_public_id=eval_res.target_public_id,
        is_global_target=eval_res.is_global_target,
        schedule_description=eval_res.schedule_description,
        is_blocked=bool(eval_res.blocking_reasons),
        future_eligibility=future_eligibility,
        governance_checks=governance_checks,
        validation_checks=validation_checks,
        blocking_reasons=eval_res.blocking_reasons,
        warnings=eval_res.warnings,
        evidence=dry_run.evidence,
    )


# --- Phase 14: Human-Triggered Bounded Automation Execution --------------


@dataclass(frozen=True)
class ManualAutomationExecutionDecision:
    allowed: bool
    automation_public_id: str
    target_action_type: str | None
    target_type: str | None
    target_public_id: str | None
    requested_by: str | None
    executor_public_id: str
    resolved_executor_role: str
    simulated_execution_attempted: bool
    blocking_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    message: str


def evaluate_manual_automation_execution(
    automation: "AdminApprovalPublic",
    *,
    executor_public_id: str,
    admin_role_overrides: Mapping[str, "AdminRole"],
) -> ManualAutomationExecutionDecision:
    """Phase 14: evaluates whether a human administrator (`executor_public_id`)
    is authorized and safe to manually trigger a single run of the underlying
    action defined by `automation`.

    Combines Phase 3 RBAC, Phase 4 governance, Phase 10-12 target policy,
    Phase 13 evaluation/dry-run, and Phase 14 allowlist/single-run enforcement.
    Never executes the target action and never writes database state.
    """
    from backend.services.admin_assistant_tool_governance import (
        Permission,
        permissions_for_role,
        resolve_admin_role,
    )
    from core_model.admin_assistant.action_registry import get_action_definition

    evaluation = evaluate_automation(
        automation, admin_role_overrides=admin_role_overrides
    )

    blocking_reasons: list[str] = list(evaluation.blocking_reasons)
    warnings: list[str] = list(evaluation.warnings)

    # Resolve executor role and permission
    executor_role = resolve_admin_role(executor_public_id, admin_role_overrides)
    executor_permissions = permissions_for_role(executor_role)

    if Permission.TOOL_EXECUTE not in executor_permissions:
        blocking_reasons.append(
            f"the executing admin ({executor_public_id!r}, resolved role "
            f"{executor_role.value!r}) lacks tool.execute permission"
        )

    # Check read-only / diagnostic action mode safety
    if evaluation.target_action_type:
        definition = get_action_definition(evaluation.target_action_type)
        if definition and definition.risk_level == "high":
            blocking_reasons.append(
                f"target action {evaluation.target_action_type!r} is high risk; "
                "manual automated execution of high-risk actions is forbidden"
            )

    allowed = (len(blocking_reasons) == 0)

    if allowed:
        message = (
            f"Manual execution of automation {automation.public_id!r} "
            f"(target action {evaluation.target_action_type!r}) is APPROVED for single-run execution."
        )
    else:
        reasons_summary = "; ".join(blocking_reasons)
        message = (
            f"Manual execution of automation {automation.public_id!r} REFUSED: {reasons_summary}."
        )

    return ManualAutomationExecutionDecision(
        allowed=allowed,
        automation_public_id=automation.public_id,
        target_action_type=evaluation.target_action_type,
        target_type=evaluation.target_type,
        target_public_id=evaluation.target_public_id,
        requested_by=automation.requested_by,
        executor_public_id=executor_public_id,
        resolved_executor_role=executor_role.value,
        simulated_execution_attempted=False,
        blocking_reasons=tuple(blocking_reasons),
        warnings=tuple(warnings),
        message=message,
    )

