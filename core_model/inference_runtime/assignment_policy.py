"""Deterministic, non-overridable assignment and public-activation policy.

A release may be assigned only if it passes every applicable gate for
its target scope; a registry-workflow fixture can never be assigned to
``internal_canary`` or ``public_chat``, and only to ``admin_diagnostic``
when a dedicated test-only setting is explicitly enabled. None of these
checks can be bypassed by an approval — approvals are checked as an
additional, separate requirement, never a substitute.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from core_model.inference_runtime import SCOPE_MINIMUM_READINESS


@dataclass(frozen=True)
class AssignmentEligibilityResult:
    eligible: bool
    blocking_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def assess_assignment_eligibility(
    *,
    scope: str,
    release_status: str,
    deployment_eligibility: str,
    evaluation_status: str,
    manifest_verified: bool,
    artifacts_verified: bool,
    checkpoint_verified: bool,
    tokenizer_verified: bool,
    model_config_matches: bool,
    has_blocking_release_issue: bool,
    is_registry_fixture: bool,
    allow_registry_fixture_diagnostics: bool = False,
    acknowledged_evaluation_warning: bool = False,
    human_review_coverage: float | None = None,
    minimum_human_review_coverage: float = 0.0,
    acknowledged_missing_human_review: bool = False,
) -> AssignmentEligibilityResult:
    blocking: list[str] = []
    warnings: list[str] = []

    if release_status != "released":
        blocking.append(f"release status '{release_status}' is not 'released'")
    if deployment_eligibility not in {"deployable", "deployable_with_warnings"}:
        blocking.append("release deployment eligibility is not_deployable")
    elif deployment_eligibility == "deployable_with_warnings":
        warnings.append("release is deployable_with_warnings")
    if not manifest_verified:
        blocking.append("release manifest does not verify")
    if not artifacts_verified:
        blocking.append("required release artifacts are not verified")
    if not checkpoint_verified:
        blocking.append("checkpoint does not verify")
    if not tokenizer_verified:
        blocking.append("tokenizer does not verify")
    if not model_config_matches:
        blocking.append("model config does not match tokenizer")
    if has_blocking_release_issue:
        blocking.append("release has an unresolved blocking issue")

    if is_registry_fixture:
        if scope in {"public_chat", "internal_canary"}:
            blocking.append(f"registry-workflow fixtures cannot be assigned to {scope}")
        elif scope == "admin_diagnostic" and not allow_registry_fixture_diagnostics:
            blocking.append(
                "registry-workflow fixtures require an explicit test-only setting "
                "to be used for admin diagnostics"
            )

    minimum_readiness = SCOPE_MINIMUM_READINESS.get(scope, frozenset())
    if evaluation_status in {"evaluation_blocked", "not_assessed"}:
        blocking.append(f"evaluation status '{evaluation_status}' blocks assignment")
    elif evaluation_status not in minimum_readiness:
        blocking.append(f"evaluation status '{evaluation_status}' does not satisfy {scope}")
    elif evaluation_status == "evaluation_warning":
        if scope == "admin_diagnostic" and not acknowledged_evaluation_warning:
            blocking.append(
                "evaluation_warning requires explicit acknowledgement for admin_diagnostic"
            )
        elif scope != "admin_diagnostic":
            blocking.append(f"{scope} requires evaluation_passed_with_limits, not a warning")

    if scope == "internal_canary":
        if human_review_coverage is None:
            if not acknowledged_missing_human_review:
                blocking.append(
                    "internal_canary requires recorded human review coverage, or explicit "
                    "acknowledgement that none has been recorded yet"
                )
            else:
                warnings.append("internal_canary proceeding without recorded human review coverage")
        elif human_review_coverage < minimum_human_review_coverage:
            blocking.append("human review coverage is below the internal_canary minimum")

    return AssignmentEligibilityResult(
        eligible=not blocking, blocking_reasons=blocking, warnings=warnings
    )


@dataclass(frozen=True)
class PublicActivationThresholds:
    max_prompt_leakage_rate: float = 0.0
    max_role_leakage_rate: float = 0.0
    max_duplicate_output_rate: float = 0.3
    minimum_human_review_coverage: float = 0.5


@dataclass(frozen=True)
class PublicActivationResult:
    activated: bool
    rejection_reasons: list[str] = field(default_factory=list)


def assess_public_activation_gate(
    *,
    scope: str,
    assignment_eligibility: AssignmentEligibilityResult,
    deployment_eligibility: str,
    evaluation_status: str,
    has_unresolved_safety_issue: bool,
    prompt_leakage_rate: float | None,
    role_leakage_rate: float | None,
    duplicate_output_rate: float | None,
    human_review_coverage: float | None,
    required_approval_roles_satisfied: bool,
    runtime_compatibility_status: str,
    runtime_health_status: str,
    admin_diagnostics_succeeded: bool,
    canary_succeeded: bool,
    canary_within_thresholds: bool,
    rollback_target_available: bool,
    fallback_policy_configured: bool,
    explicit_activation_confirmed: bool,
    thresholds: PublicActivationThresholds | None = None,
) -> PublicActivationResult:
    """Phase 15 must not fabricate a passing release merely to test public
    activation — every requirement below demands real, present evidence;
    a missing measurement (``None``) fails the gate, it never passes it."""

    thresholds = thresholds or PublicActivationThresholds()
    reasons: list[str] = []
    if scope != "public_chat":
        reasons.append("activation gate only applies to the public_chat scope")
    if not assignment_eligibility.eligible:
        reasons.extend(assignment_eligibility.blocking_reasons)
    if deployment_eligibility != "deployable":
        reasons.append("release deployment eligibility must be exactly 'deployable'")
    if evaluation_status != "evaluation_passed_with_limits":
        reasons.append("evaluation status must be evaluation_passed_with_limits")
    if has_unresolved_safety_issue:
        reasons.append("an unresolved safety issue exists")
    if prompt_leakage_rate is None or prompt_leakage_rate > thresholds.max_prompt_leakage_rate:
        reasons.append("prompt leakage rate exceeds threshold or is unmeasured")
    if role_leakage_rate is None or role_leakage_rate > thresholds.max_role_leakage_rate:
        reasons.append("role leakage rate exceeds threshold or is unmeasured")
    if (
        duplicate_output_rate is None
        or duplicate_output_rate > thresholds.max_duplicate_output_rate
    ):
        reasons.append("duplicate output rate exceeds threshold or is unmeasured")
    if (
        human_review_coverage is None
        or human_review_coverage < thresholds.minimum_human_review_coverage
    ):
        reasons.append("human review coverage is missing or below the public-chat minimum")
    if not required_approval_roles_satisfied:
        reasons.append("required public-chat approval roles are not satisfied")
    if runtime_compatibility_status != "compatible":
        reasons.append("runtime compatibility must be exactly 'compatible'")
    if runtime_health_status != "healthy":
        reasons.append("runtime health must be exactly 'healthy'")
    if not admin_diagnostics_succeeded:
        reasons.append("successful admin diagnostics have not been recorded")
    if not canary_succeeded or not canary_within_thresholds:
        reasons.append("canary has not succeeded within configured thresholds")
    if not rollback_target_available:
        reasons.append("no verified rollback target is available")
    if not fallback_policy_configured:
        reasons.append("fallback policy is not configured")
    if not explicit_activation_confirmed:
        reasons.append("explicit activation confirmation was not provided")

    return PublicActivationResult(activated=not reasons, rejection_reasons=reasons)
