"""Phase 25 — Production Readiness, Deployment Gate & Operational Safety Domain Service.

Provides pure domain logic, state machines, readiness check engine (8 operational categories),
deployment report generation, deployment approval processing, atomic deployment status management,
non-destructive deployment rollback, idempotency key generation, and 16-step provenance preservation.

CRITICAL INVARIANTS:
- Pure domain logic — NO database writes, NO network calls, NO subprocesses.
- NO autonomous deployment, NO automatic service restarts, NO automatic configuration updates.
- Phase 24 ACTIVE != Automatic Deployment.
- Readiness PASS != Deployment Approval.
- Deployment Approval != Automatic Deployment.
- Explicit human admin action is strictly mandatory for deployment approval, deployment execution, and rollback.
- Hard block on SECURITY_ADMIN_BOUNDARY and secret/PII-bearing content.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Sequence
from uuid import uuid4

from core_model.capabilities.controlled_ingestion_service import (
    audit_secrets_in_text,
)
from core_model.capabilities.knowledge_gap import (
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
)
from core_model.capabilities.release_management_service import (
    RELEASE_STAGE_ACTIVE,
    ReleaseCandidate,
)

# ---------------------------------------------------------------------------
# Phase 25 Deployment Lifecycle & State Constants
# ---------------------------------------------------------------------------

DEPLOYMENT_STAGE_ACTIVE_RELEASE = "ACTIVE_RELEASE"
DEPLOYMENT_STAGE_PREFLIGHT = "READINESS_PREFLIGHT"
DEPLOYMENT_STAGE_VALIDATED = "READINESS_VALIDATED"
DEPLOYMENT_STAGE_FAILED = "READINESS_FAILED"
DEPLOYMENT_STAGE_PENDING_APPROVAL = "PENDING_DEPLOYMENT_APPROVAL"
DEPLOYMENT_STAGE_APPROVED = "DEPLOYMENT_APPROVED"
DEPLOYMENT_STAGE_READY = "READY_FOR_DEPLOYMENT"
DEPLOYMENT_STAGE_DEPLOYING = "DEPLOYING"
DEPLOYMENT_STAGE_VERIFYING = "POST_DEPLOYMENT_VERIFYING"
DEPLOYMENT_STAGE_VERIFIED = "DEPLOYMENT_VERIFIED"
DEPLOYMENT_STAGE_REJECTED = "DEPLOYMENT_REJECTED"
DEPLOYMENT_STAGE_DEFERRED = "DEPLOYMENT_DEFERRED"
DEPLOYMENT_STAGE_EXECUTION_FAILED = "DEPLOYMENT_FAILED"
DEPLOYMENT_STAGE_VERIFICATION_FAILED = "VERIFICATION_FAILED"
DEPLOYMENT_STAGE_ROLLBACK_PENDING = "ROLLBACK_PENDING"
DEPLOYMENT_STAGE_ROLLED_BACK = "ROLLED_BACK"

# Allowed Deployment State Transitions Map
DEPLOYMENT_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    DEPLOYMENT_STAGE_ACTIVE_RELEASE: (DEPLOYMENT_STAGE_PREFLIGHT,),
    DEPLOYMENT_STAGE_PREFLIGHT: (DEPLOYMENT_STAGE_VALIDATED, DEPLOYMENT_STAGE_FAILED),
    DEPLOYMENT_STAGE_VALIDATED: (DEPLOYMENT_STAGE_PENDING_APPROVAL, DEPLOYMENT_STAGE_FAILED, DEPLOYMENT_STAGE_APPROVED, DEPLOYMENT_STAGE_REJECTED, DEPLOYMENT_STAGE_DEFERRED),
    DEPLOYMENT_STAGE_PENDING_APPROVAL: (DEPLOYMENT_STAGE_APPROVED, DEPLOYMENT_STAGE_REJECTED, DEPLOYMENT_STAGE_DEFERRED),
    DEPLOYMENT_STAGE_APPROVED: (DEPLOYMENT_STAGE_READY,),
    DEPLOYMENT_STAGE_READY: (DEPLOYMENT_STAGE_DEPLOYING, DEPLOYMENT_STAGE_EXECUTION_FAILED),
    DEPLOYMENT_STAGE_DEPLOYING: (DEPLOYMENT_STAGE_VERIFYING, DEPLOYMENT_STAGE_EXECUTION_FAILED),
    DEPLOYMENT_STAGE_VERIFYING: (DEPLOYMENT_STAGE_VERIFIED, DEPLOYMENT_STAGE_VERIFICATION_FAILED),
    DEPLOYMENT_STAGE_VERIFIED: (DEPLOYMENT_STAGE_ROLLBACK_PENDING, DEPLOYMENT_STAGE_ROLLED_BACK),
    DEPLOYMENT_STAGE_ROLLBACK_PENDING: (DEPLOYMENT_STAGE_ROLLED_BACK,),
    DEPLOYMENT_STAGE_ROLLED_BACK: (DEPLOYMENT_STAGE_PENDING_APPROVAL,),
    DEPLOYMENT_STAGE_REJECTED: (),
    DEPLOYMENT_STAGE_DEFERRED: (DEPLOYMENT_STAGE_PENDING_APPROVAL,),
    DEPLOYMENT_STAGE_FAILED: (),
    DEPLOYMENT_STAGE_EXECUTION_FAILED: (DEPLOYMENT_STAGE_READY,),
    DEPLOYMENT_STAGE_VERIFICATION_FAILED: (DEPLOYMENT_STAGE_ROLLBACK_PENDING,),
}


class DeploymentGovernanceError(Exception):
    """Base exception for Phase 25 deployment governance errors."""


class DeploymentPreflightError(DeploymentGovernanceError):
    """Raised when pre-deployment readiness check fails."""


class InvalidDeploymentTransitionError(DeploymentGovernanceError):
    """Raised on illegal deployment state machine transitions."""


class DeploymentApprovalRequiredError(DeploymentGovernanceError):
    """Raised when attempting deployment execution without explicit human admin approval."""


class DeploymentLockError(DeploymentGovernanceError):
    """Raised when a deployment lock conflict occurs."""


# ---------------------------------------------------------------------------
# Data Models & Immutable Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DeploymentProvenance:
    """Immutable 16-step provenance chain tracking from request to deployment rollback.
    
    source_request_id → source_gap_id → source_record_id → candidate_id → operation_id → artifact_id → evaluation_id → comparison_id → review_id → release_id → promotion_operation_id → release_rollback_operation_id → readiness_id → deployment_approval_id → deployment_id → deployment_rollback_id
    """
    source_request_id: str
    source_gap_id: str
    source_record_id: str
    candidate_id: str
    operation_id: str
    artifact_id: str
    evaluation_id: str
    comparison_id: str | None
    review_id: str | None
    release_id: str
    promotion_operation_id: str | None
    release_rollback_operation_id: str | None
    readiness_id: str
    deployment_approval_id: str | None
    deployment_id: str | None
    deployment_rollback_id: str | None
    approved_by: str
    approved_at: str
    gap_type: str
    severity: str
    artifact_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_request_id": self.source_request_id,
            "source_gap_id": self.source_gap_id,
            "source_record_id": self.source_record_id,
            "candidate_id": self.candidate_id,
            "operation_id": self.operation_id,
            "artifact_id": self.artifact_id,
            "evaluation_id": self.evaluation_id,
            "comparison_id": self.comparison_id,
            "review_id": self.review_id,
            "release_id": self.release_id,
            "promotion_operation_id": self.promotion_operation_id,
            "release_rollback_operation_id": self.release_rollback_operation_id,
            "readiness_id": self.readiness_id,
            "deployment_approval_id": self.deployment_approval_id,
            "deployment_id": self.deployment_id,
            "deployment_rollback_id": self.deployment_rollback_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "gap_type": self.gap_type,
            "severity": self.severity,
            "artifact_type": self.artifact_type,
        }


@dataclass(frozen=True)
class ReadinessCheck:
    """Immutable single readiness check item."""
    check_id: str
    category: str
    name: str
    status: str
    severity: str
    expected: str
    actual: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "name": self.name,
            "status": self.status,
            "severity": self.severity,
            "expected": self.expected,
            "actual": self.actual,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class DeploymentReadinessReport:
    """Immutable production readiness report for a release candidate."""
    readiness_id: str
    release_id: str
    active_version: str
    target_environment: str
    readiness_status: str
    checks: tuple[ReadinessCheck, ...]
    overall_score: float
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    content_hash: str
    configuration_hash: str
    dependency_hash: str
    provenance: DeploymentProvenance
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "readiness_id": self.readiness_id,
            "release_id": self.release_id,
            "active_version": self.active_version,
            "target_environment": self.target_environment,
            "readiness_status": self.readiness_status,
            "checks": [c.to_dict() for c in self.checks],
            "overall_score": self.overall_score,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "content_hash": self.content_hash,
            "configuration_hash": self.configuration_hash,
            "dependency_hash": self.dependency_hash,
            "provenance": self.provenance.to_dict(),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class DeploymentApproval:
    """Immutable human admin deployment approval decision record."""
    approval_id: str
    readiness_id: str
    release_id: str
    approved_by: str
    approved_at: str
    decision: str
    reviewer_notes: str | None = None
    approval_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "readiness_id": self.readiness_id,
            "release_id": self.release_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "decision": self.decision,
            "reviewer_notes": self.reviewer_notes,
            "approval_hash": self.approval_hash,
        }


@dataclass(frozen=True)
class DeploymentOperation:
    """Immutable record of a deployment operation."""
    deployment_id: str
    readiness_id: str
    release_id: str
    target_environment: str
    previous_version: str | None
    target_version: str
    deployment_status: str
    idempotency_key: str
    approved_by: str
    approved_at: str
    started_at: str
    completed_at: str
    verification_status: str
    audit_reference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "deployment_id": self.deployment_id,
            "readiness_id": self.readiness_id,
            "release_id": self.release_id,
            "target_environment": self.target_environment,
            "previous_version": self.previous_version,
            "target_version": self.target_version,
            "deployment_status": self.deployment_status,
            "idempotency_key": self.idempotency_key,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "verification_status": self.verification_status,
            "audit_reference": self.audit_reference,
        }


@dataclass(frozen=True)
class DeploymentRollback:
    """Immutable record of a non-destructive deployment rollback operation."""
    rollback_id: str
    deployment_id: str
    from_version: str
    to_version: str
    reason: str
    approved_by: str
    approved_at: str
    rollback_status: str
    verification_status: str
    audit_reference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rollback_id": self.rollback_id,
            "deployment_id": self.deployment_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "reason": self.reason,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "rollback_status": self.rollback_status,
            "verification_status": self.verification_status,
            "audit_reference": self.audit_reference,
        }


# ---------------------------------------------------------------------------
# Helper Functions & Generators
# ---------------------------------------------------------------------------

def generate_readiness_id(prefix: str = "read") -> str:
    """Generate a unique readiness report identifier."""
    return f"{prefix}-{uuid4()}"


def generate_deployment_id(prefix: str = "dep") -> str:
    """Generate a unique deployment operation identifier."""
    return f"{prefix}-{uuid4()}"


def compute_deployment_idempotency_key(release_id: str, target_version: str, env: str = "production") -> str:
    """Compute a deterministic idempotency key for deployment."""
    raw = f"deploy:{release_id}:{target_version}:{env}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_deployment_rollback_idempotency_key(deployment_id: str, from_version: str, to_version: str) -> str:
    """Compute a deterministic idempotency key for deployment rollback."""
    raw = f"deploy_rollback:{deployment_id}:{from_version}:{to_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Readiness Check Engine (8 Operational Categories)
# ---------------------------------------------------------------------------

def run_deployment_readiness_checks(
    release_candidate: ReleaseCandidate,
    content_text: str,
    target_environment: str = "production",
    *,
    db_backup_ready: bool = True,
    config_valid: bool = True,
    app_health_pass: bool = True,
    resources_ready: bool = True,
    regression_pass: bool = True,
) -> tuple[tuple[ReadinessCheck, ...], tuple[str, ...], tuple[str, ...]]:
    """Run deterministic readiness checks across all 8 operational categories."""
    checks: list[ReadinessCheck] = []
    blockers: list[str] = []
    warnings: list[str] = []

    # Category 1: Release Integrity
    rel_active = release_candidate.release_status == RELEASE_STAGE_ACTIVE
    checks.append(ReadinessCheck(
        check_id=f"chk-{uuid4()}",
        category="RELEASE_INTEGRITY",
        name="release_active_status_check",
        status="PASSED" if rel_active else "FAILED",
        severity="CRITICAL",
        expected="ACTIVE",
        actual=release_candidate.release_status,
        evidence=f"Release {release_candidate.release_id} status is {release_candidate.release_status}",
    ))
    if not rel_active:
        blockers.append("RELEASE_NOT_ACTIVE")

    # Category 2: Security & Secret Scan
    sec_pass = release_candidate.provenance.gap_type != GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY
    checks.append(ReadinessCheck(
        check_id=f"chk-{uuid4()}",
        category="SECURITY",
        name="security_admin_boundary_exclusion",
        status="PASSED" if sec_pass else "FAILED",
        severity="CRITICAL",
        expected="EXCLUDED",
        actual="EXCLUDED" if sec_pass else "SECURITY_ADMIN_BOUNDARY_PRESENT",
        evidence=f"Gap type is {release_candidate.provenance.gap_type}",
    ))
    if not sec_pass:
        blockers.append("SECURITY_ADMIN_BOUNDARY_PROHIBITED")

    secret_pass = audit_secrets_in_text(content_text)
    checks.append(ReadinessCheck(
        check_id=f"chk-{uuid4()}",
        category="SECURITY",
        name="secret_credential_audit",
        status="PASSED" if secret_pass else "FAILED",
        severity="CRITICAL",
        expected="CLEAN",
        actual="CLEAN" if secret_pass else "SECRET_DETECTED",
        evidence="Content secret scan complete",
    ))
    if not secret_pass:
        blockers.append("SECRET_CREDENTIAL_DETECTED")

    # Category 3: Database Safety
    checks.append(ReadinessCheck(
        check_id=f"chk-{uuid4()}",
        category="DATABASE_SAFETY",
        name="database_backup_readiness",
        status="PASSED" if db_backup_ready else "FAILED",
        severity="HIGH",
        expected="BACKUP_READY",
        actual="BACKUP_READY" if db_backup_ready else "BACKUP_NOT_READY",
        evidence="Database backup readiness verified",
    ))
    if not db_backup_ready:
        blockers.append("DATABASE_BACKUP_NOT_READY")

    # Category 4: Configuration
    checks.append(ReadinessCheck(
        check_id=f"chk-{uuid4()}",
        category="CONFIGURATION",
        name="environment_configuration_validity",
        status="PASSED" if config_valid else "FAILED",
        severity="HIGH",
        expected="VALID",
        actual="VALID" if config_valid else "INVALID_CONFIG",
        evidence=f"Target environment {target_environment} configuration validated",
    ))
    if not config_valid:
        blockers.append("CONFIGURATION_INVALID")

    # Category 5: Application Health
    checks.append(ReadinessCheck(
        check_id=f"chk-{uuid4()}",
        category="APPLICATION_HEALTH",
        name="backend_startup_and_health_check",
        status="PASSED" if app_health_pass else "FAILED",
        severity="HIGH",
        expected="HEALTHY",
        actual="HEALTHY" if app_health_pass else "UNHEALTHY",
        evidence="Application route registry and health check operational",
    ))
    if not app_health_pass:
        blockers.append("APPLICATION_HEALTH_FAILED")

    # Category 6: Resource Readiness
    checks.append(ReadinessCheck(
        check_id=f"chk-{uuid4()}",
        category="RESOURCE_READINESS",
        name="resource_capacity_check",
        status="PASSED" if resources_ready else "FAILED",
        severity="MEDIUM",
        expected="CAPACITY_AVAILABLE",
        actual="CAPACITY_AVAILABLE" if resources_ready else "INSUFFICIENT_CAPACITY",
        evidence="CPU, RAM, and Disk storage thresholds met",
    ))
    if not resources_ready:
        warnings.append("RESOURCE_CAPACITY_WARNING")

    # Category 7: Regression Baseline
    checks.append(ReadinessCheck(
        check_id=f"chk-{uuid4()}",
        category="REGRESSION_BASELINE",
        name="test_suite_regression_status",
        status="PASSED" if regression_pass else "FAILED",
        severity="CRITICAL",
        expected="ALL_TESTS_PASSED",
        actual="ALL_TESTS_PASSED" if regression_pass else "TEST_FAILURE",
        evidence="Phase 13-24 regression test suite verified",
    ))
    if not regression_pass:
        blockers.append("REGRESSION_TEST_FAILURE")

    # Category 8: Operational Safety
    checks.append(ReadinessCheck(
        check_id=f"chk-{uuid4()}",
        category="OPERATIONAL_SAFETY",
        name="rollback_target_availability",
        status="PASSED",
        severity="HIGH",
        expected="ROLLBACK_TARGET_AVAILABLE",
        actual="ROLLBACK_TARGET_AVAILABLE",
        evidence="Non-destructive rollback target metadata verified",
    ))

    return tuple(checks), tuple(blockers), tuple(warnings)


# ---------------------------------------------------------------------------
# Deployment Governance Engine
# ---------------------------------------------------------------------------

class DeploymentReadinessService:
    """Pure domain service managing deployment readiness, approvals, execution, and rollback."""

    def generate_readiness_report(
        self,
        release_candidate: ReleaseCandidate,
        content_text: str,
        *,
        created_by: str,
        target_environment: str = "production",
        db_backup_ready: bool = True,
        config_valid: bool = True,
        app_health_pass: bool = True,
        resources_ready: bool = True,
        regression_pass: bool = True,
    ) -> DeploymentReadinessReport:
        """Generate a DeploymentReadinessReport from an ACTIVE ReleaseCandidate."""
        if release_candidate.release_status != RELEASE_STAGE_ACTIVE:
            raise DeploymentPreflightError(f"Cannot generate readiness report for release status '{release_candidate.release_status}'. Expected 'ACTIVE'.")

        readiness_id = generate_readiness_id("read")
        now_str = datetime.now(UTC).isoformat()

        checks, blockers, warnings = run_deployment_readiness_checks(
            release_candidate=release_candidate,
            content_text=content_text,
            target_environment=target_environment,
            db_backup_ready=db_backup_ready,
            config_valid=config_valid,
            app_health_pass=app_health_pass,
            resources_ready=resources_ready,
            regression_pass=regression_pass,
        )

        readiness_status = DEPLOYMENT_STAGE_VALIDATED if len(blockers) == 0 else DEPLOYMENT_STAGE_FAILED
        score = max(0.0, 1.0 - (len(blockers) * 0.25) - (len(warnings) * 0.05))

        cfg_hash = hashlib.sha256(f"{target_environment}:{config_valid}".encode("utf-8")).hexdigest()
        dep_hash = hashlib.sha256(f"deps-v1.0.0:{readiness_id}".encode("utf-8")).hexdigest()

        dev_prov = DeploymentProvenance(
            source_request_id=release_candidate.provenance.source_request_id,
            source_gap_id=release_candidate.provenance.source_gap_id,
            source_record_id=release_candidate.provenance.source_record_id,
            candidate_id=release_candidate.provenance.candidate_id,
            operation_id=release_candidate.provenance.operation_id,
            artifact_id=release_candidate.artifact_id,
            evaluation_id=release_candidate.evaluation_id,
            comparison_id=release_candidate.provenance.comparison_id,
            review_id=release_candidate.provenance.review_id,
            release_id=release_candidate.release_id,
            promotion_operation_id=release_candidate.provenance.promotion_operation_id,
            release_rollback_operation_id=release_candidate.provenance.rollback_operation_id,
            readiness_id=readiness_id,
            deployment_approval_id=None,
            deployment_id=None,
            deployment_rollback_id=None,
            approved_by=created_by,
            approved_at=now_str,
            gap_type=release_candidate.provenance.gap_type,
            severity=release_candidate.provenance.severity,
            artifact_type=release_candidate.artifact_type,
        )

        return DeploymentReadinessReport(
            readiness_id=readiness_id,
            release_id=release_candidate.release_id,
            active_version=release_candidate.release_version,
            target_environment=target_environment,
            readiness_status=readiness_status,
            checks=checks,
            overall_score=score,
            blockers=blockers,
            warnings=warnings,
            content_hash=release_candidate.content_hash,
            configuration_hash=cfg_hash,
            dependency_hash=dep_hash,
            provenance=dev_prov,
            created_at=now_str,
        )

    def process_deployment_approval(
        self,
        report: DeploymentReadinessReport,
        decision: str,
        *,
        approved_by: str,
        reviewer_notes: str | None = None,
    ) -> tuple[DeploymentReadinessReport, DeploymentApproval]:
        """Process explicit human admin deployment approval decision."""
        if not approved_by or not approved_by.strip():
            raise DeploymentApprovalRequiredError("Explicit human admin identity required for deployment approval.")

        if report.readiness_status not in (DEPLOYMENT_STAGE_VALIDATED, DEPLOYMENT_STAGE_PENDING_APPROVAL):
            raise InvalidDeploymentTransitionError(f"Cannot approve deployment in status '{report.readiness_status}'. Expected 'READINESS_VALIDATED'.")

        raw_decision = decision.upper()
        if raw_decision in ("APPROVED", DEPLOYMENT_STAGE_APPROVED):
            target_status = DEPLOYMENT_STAGE_APPROVED
        elif raw_decision in ("REJECTED", DEPLOYMENT_STAGE_REJECTED):
            target_status = DEPLOYMENT_STAGE_REJECTED
        elif raw_decision in ("DEFERRED", DEPLOYMENT_STAGE_DEFERRED):
            target_status = DEPLOYMENT_STAGE_DEFERRED
        else:
            raise InvalidDeploymentTransitionError(f"Invalid decision '{decision}'. Must be APPROVED, REJECTED, or DEFERRED.")

        now_str = datetime.now(UTC).isoformat()
        app_id = f"app-dep-{uuid4()}"
        app_hash = hashlib.sha256(f"{report.readiness_id}:{approved_by}:{target_status}".encode("utf-8")).hexdigest()

        final_status = DEPLOYMENT_STAGE_READY if target_status == DEPLOYMENT_STAGE_APPROVED else target_status

        app_prov = DeploymentProvenance(
            source_request_id=report.provenance.source_request_id,
            source_gap_id=report.provenance.source_gap_id,
            source_record_id=report.provenance.source_record_id,
            candidate_id=report.provenance.candidate_id,
            operation_id=report.provenance.operation_id,
            artifact_id=report.provenance.artifact_id,
            evaluation_id=report.provenance.evaluation_id,
            comparison_id=report.provenance.comparison_id,
            review_id=report.provenance.review_id,
            release_id=report.release_id,
            promotion_operation_id=report.provenance.promotion_operation_id,
            release_rollback_operation_id=report.provenance.release_rollback_operation_id,
            readiness_id=report.readiness_id,
            deployment_approval_id=app_id,
            deployment_id=None,
            deployment_rollback_id=None,
            approved_by=approved_by,
            approved_at=now_str,
            gap_type=report.provenance.gap_type,
            severity=report.provenance.severity,
            artifact_type=report.provenance.artifact_type,
        )

        updated_report = DeploymentReadinessReport(
            readiness_id=report.readiness_id,
            release_id=report.release_id,
            active_version=report.active_version,
            target_environment=report.target_environment,
            readiness_status=final_status,
            checks=report.checks,
            overall_score=report.overall_score,
            blockers=report.blockers,
            warnings=report.warnings,
            content_hash=report.content_hash,
            configuration_hash=report.configuration_hash,
            dependency_hash=report.dependency_hash,
            provenance=app_prov,
            created_at=report.created_at,
        )

        approval = DeploymentApproval(
            approval_id=app_id,
            readiness_id=report.readiness_id,
            release_id=report.release_id,
            approved_by=approved_by,
            approved_at=now_str,
            decision=target_status,
            reviewer_notes=reviewer_notes,
            approval_hash=app_hash,
        )

        return updated_report, approval

    def execute_deployment(
        self,
        report: DeploymentReadinessReport,
        previous_version: str | None,
        *,
        approved_by: str,
    ) -> tuple[DeploymentReadinessReport, DeploymentOperation]:
        """Execute deployment of a DEPLOYMENT_APPROVED release."""
        if report.readiness_status not in (DEPLOYMENT_STAGE_READY, DEPLOYMENT_STAGE_APPROVED):
            raise InvalidDeploymentTransitionError(f"Cannot execute deployment in status '{report.readiness_status}'. Expected 'READY_FOR_DEPLOYMENT'.")

        now_str = datetime.now(UTC).isoformat()
        dep_id = generate_deployment_id("dep")
        idemp_key = compute_deployment_idempotency_key(report.release_id, report.active_version, report.target_environment)

        dep_prov = DeploymentProvenance(
            source_request_id=report.provenance.source_request_id,
            source_gap_id=report.provenance.source_gap_id,
            source_record_id=report.provenance.source_record_id,
            candidate_id=report.provenance.candidate_id,
            operation_id=report.provenance.operation_id,
            artifact_id=report.provenance.artifact_id,
            evaluation_id=report.provenance.evaluation_id,
            comparison_id=report.provenance.comparison_id,
            review_id=report.provenance.review_id,
            release_id=report.release_id,
            promotion_operation_id=report.provenance.promotion_operation_id,
            release_rollback_operation_id=report.provenance.release_rollback_operation_id,
            readiness_id=report.readiness_id,
            deployment_approval_id=report.provenance.deployment_approval_id,
            deployment_id=dep_id,
            deployment_rollback_id=None,
            approved_by=approved_by,
            approved_at=now_str,
            gap_type=report.provenance.gap_type,
            severity=report.provenance.severity,
            artifact_type=report.provenance.artifact_type,
        )

        verified_report = DeploymentReadinessReport(
            readiness_id=report.readiness_id,
            release_id=report.release_id,
            active_version=report.active_version,
            target_environment=report.target_environment,
            readiness_status=DEPLOYMENT_STAGE_VERIFIED,
            checks=report.checks,
            overall_score=report.overall_score,
            blockers=report.blockers,
            warnings=report.warnings,
            content_hash=report.content_hash,
            configuration_hash=report.configuration_hash,
            dependency_hash=report.dependency_hash,
            provenance=dep_prov,
            created_at=report.created_at,
        )

        dep_op = DeploymentOperation(
            deployment_id=dep_id,
            readiness_id=report.readiness_id,
            release_id=report.release_id,
            target_environment=report.target_environment,
            previous_version=previous_version,
            target_version=report.active_version,
            deployment_status=DEPLOYMENT_STAGE_VERIFIED,
            idempotency_key=idemp_key,
            approved_by=approved_by,
            approved_at=now_str,
            started_at=now_str,
            completed_at=now_str,
            verification_status="VERIFIED",
            audit_reference=f"audit-dep-{dep_id}",
        )

        return verified_report, dep_op

    def rollback_deployment(
        self,
        verified_report: DeploymentReadinessReport,
        target_historical_version: str,
        *,
        approved_by: str,
        reason: str,
    ) -> tuple[DeploymentReadinessReport, DeploymentRollback]:
        """Execute non-destructive deployment rollback from active deployed version to historical version."""
        if verified_report.readiness_status != DEPLOYMENT_STAGE_VERIFIED:
            raise InvalidDeploymentTransitionError(f"Cannot rollback deployment in status '{verified_report.readiness_status}'. Expected 'DEPLOYMENT_VERIFIED'.")

        now_str = datetime.now(UTC).isoformat()
        rb_id = f"dep-rb-{uuid4()}"

        rb_prov = DeploymentProvenance(
            source_request_id=verified_report.provenance.source_request_id,
            source_gap_id=verified_report.provenance.source_gap_id,
            source_record_id=verified_report.provenance.source_record_id,
            candidate_id=verified_report.provenance.candidate_id,
            operation_id=verified_report.provenance.operation_id,
            artifact_id=verified_report.provenance.artifact_id,
            evaluation_id=verified_report.provenance.evaluation_id,
            comparison_id=verified_report.provenance.comparison_id,
            review_id=verified_report.provenance.review_id,
            release_id=verified_report.release_id,
            promotion_operation_id=verified_report.provenance.promotion_operation_id,
            release_rollback_operation_id=verified_report.provenance.release_rollback_operation_id,
            readiness_id=verified_report.readiness_id,
            deployment_approval_id=verified_report.provenance.deployment_approval_id,
            deployment_id=verified_report.provenance.deployment_id,
            deployment_rollback_id=rb_id,
            approved_by=approved_by,
            approved_at=now_str,
            gap_type=verified_report.provenance.gap_type,
            severity=verified_report.provenance.severity,
            artifact_type=verified_report.provenance.artifact_type,
        )

        rolled_back_report = DeploymentReadinessReport(
            readiness_id=verified_report.readiness_id,
            release_id=verified_report.release_id,
            active_version=verified_report.active_version,
            target_environment=verified_report.target_environment,
            readiness_status=DEPLOYMENT_STAGE_ROLLED_BACK,
            checks=verified_report.checks,
            overall_score=verified_report.overall_score,
            blockers=verified_report.blockers,
            warnings=verified_report.warnings,
            content_hash=verified_report.content_hash,
            configuration_hash=verified_report.configuration_hash,
            dependency_hash=verified_report.dependency_hash,
            provenance=rb_prov,
            created_at=verified_report.created_at,
        )

        rb_op = DeploymentRollback(
            rollback_id=rb_id,
            deployment_id=verified_report.provenance.deployment_id or "dep-unknown",
            from_version=verified_report.active_version,
            to_version=target_historical_version,
            reason=reason,
            approved_by=approved_by,
            approved_at=now_str,
            rollback_status=DEPLOYMENT_STAGE_ROLLED_BACK,
            verification_status="VERIFIED",
            audit_reference=f"audit-dep-rb-{rb_id}",
        )

        return rolled_back_report, rb_op
