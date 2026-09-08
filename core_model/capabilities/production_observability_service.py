"""Phase 26 — Production Observability, Runtime Health, Incident Detection & Human-Governed Recovery Service.

Implements pure domain models, health check engine, health trend comparison,
incident detection state machine, recovery recommendation engine, and human-governed recovery execution.

NON-AUTONOMOUS INVARIANT:
HEALTH ALERT != AUTOMATIC REMEDIATION
INCIDENT DETECTED != AUTOMATIC RECOVERY
RECOVERY RECOMMENDATION != RECOVERY EXECUTION
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

# Incident State Machine Constants
INCIDENT_STAGE_DETECTED = "INCIDENT_DETECTED"
INCIDENT_STAGE_ACKNOWLEDGED = "ACKNOWLEDGED"
INCIDENT_STAGE_INVESTIGATING = "INVESTIGATING"
INCIDENT_STAGE_RECOMMENDED = "RECOVERY_RECOMMENDED"
INCIDENT_STAGE_PENDING_HUMAN = "PENDING_HUMAN_ACTION"
INCIDENT_STAGE_APPROVED = "RECOVERY_APPROVED"
INCIDENT_STAGE_EXECUTING = "RECOVERY_EXECUTING"
INCIDENT_STAGE_VERIFIED = "RECOVERY_VERIFIED"
INCIDENT_STAGE_REJECTED = "RECOVERY_REJECTED"
INCIDENT_STAGE_DEFERRED = "RECOVERY_DEFERRED"
INCIDENT_STAGE_FAILED = "RECOVERY_FAILED"
INCIDENT_STAGE_VERIFICATION_FAILED = "VERIFICATION_FAILED"
INCIDENT_STAGE_RESOLVED = "RESOLVED"
INCIDENT_STAGE_CLOSED = "CLOSED"

# Allowed Incident Transitions Map
INCIDENT_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    INCIDENT_STAGE_DETECTED: (INCIDENT_STAGE_ACKNOWLEDGED, INCIDENT_STAGE_CLOSED),
    INCIDENT_STAGE_ACKNOWLEDGED: (INCIDENT_STAGE_INVESTIGATING, INCIDENT_STAGE_RECOMMENDED, INCIDENT_STAGE_CLOSED),
    INCIDENT_STAGE_INVESTIGATING: (INCIDENT_STAGE_RECOMMENDED, INCIDENT_STAGE_CLOSED),
    INCIDENT_STAGE_RECOMMENDED: (INCIDENT_STAGE_PENDING_HUMAN, INCIDENT_STAGE_REJECTED, INCIDENT_STAGE_DEFERRED),
    INCIDENT_STAGE_PENDING_HUMAN: (INCIDENT_STAGE_APPROVED, INCIDENT_STAGE_REJECTED, INCIDENT_STAGE_DEFERRED),
    INCIDENT_STAGE_APPROVED: (INCIDENT_STAGE_EXECUTING, INCIDENT_STAGE_FAILED),
    INCIDENT_STAGE_EXECUTING: (INCIDENT_STAGE_VERIFIED, INCIDENT_STAGE_FAILED),
    INCIDENT_STAGE_VERIFIED: (INCIDENT_STAGE_RESOLVED, INCIDENT_STAGE_VERIFICATION_FAILED),
    INCIDENT_STAGE_REJECTED: (INCIDENT_STAGE_CLOSED,),
    INCIDENT_STAGE_DEFERRED: (INCIDENT_STAGE_PENDING_HUMAN, INCIDENT_STAGE_CLOSED),
    INCIDENT_STAGE_FAILED: (INCIDENT_STAGE_PENDING_HUMAN, INCIDENT_STAGE_CLOSED),
    INCIDENT_STAGE_VERIFICATION_FAILED: (INCIDENT_STAGE_PENDING_HUMAN, INCIDENT_STAGE_CLOSED),
    INCIDENT_STAGE_RESOLVED: (INCIDENT_STAGE_CLOSED,),
    INCIDENT_STAGE_CLOSED: (),
}


class ObservabilityError(Exception):
    """Base exception for Phase 26 domain errors."""


class InvalidIncidentTransitionError(ObservabilityError):
    """Raised when invalid state machine transition is attempted."""


class RecoveryApprovalRequiredError(ObservabilityError):
    """Raised when recovery action lacks explicit human approval."""


class RecoveryLockError(ObservabilityError):
    """Raised when recovery lock acquisition fails."""


@dataclass(frozen=True)
class ObservabilityProvenance:
    """16-Step extended provenance chain."""

    source_request_id: str | None
    source_gap_id: str | None
    source_record_id: str | None
    candidate_id: str | None
    operation_id: str | None
    artifact_id: str | None
    evaluation_id: str | None
    comparison_id: str | None
    review_id: str | None
    release_id: str
    promotion_operation_id: str | None
    deployment_id: str
    health_report_id: str | None
    health_check_id: str | None
    incident_id: str | None
    recovery_id: str | None

    def to_dict(self) -> dict[str, str | None]:
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
            "deployment_id": self.deployment_id,
            "health_report_id": self.health_report_id,
            "health_check_id": self.health_check_id,
            "incident_id": self.incident_id,
            "recovery_id": self.recovery_id,
        }


@dataclass(frozen=True)
class HealthCheckItem:
    """Single health check observation."""

    check_id: str
    category: str
    component: str
    status: str  # HEALTHY, DEGRADED, UNHEALTHY, UNKNOWN, BLOCKED
    severity: str  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    observed_value: str
    expected_value: str
    timestamp: str
    evidence: str

    def to_dict(self) -> dict[str, str]:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "component": self.component,
            "status": self.status,
            "severity": self.severity,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "timestamp": self.timestamp,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class RuntimeHealthReport:
    """Immutable runtime health observation report."""

    health_report_id: str
    deployment_id: str
    release_id: str
    active_version: str
    overall_status: str  # HEALTHY, DEGRADED, UNHEALTHY, BLOCKED
    health_score: float  # 0.0 to 1.0
    checks: tuple[HealthCheckItem, ...]
    created_at: str
    provenance: ObservabilityProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "health_report_id": self.health_report_id,
            "deployment_id": self.deployment_id,
            "release_id": self.release_id,
            "active_version": self.active_version,
            "overall_status": self.overall_status,
            "health_score": self.health_score,
            "checks": [c.to_dict() for c in self.checks],
            "created_at": self.created_at,
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True)
class HealthTrendComparison:
    """Comparison between two historical health reports."""

    comparison_id: str
    report_id_a: str
    report_id_b: str
    trend_status: str  # HEALTH_IMPROVED, HEALTH_STABLE, HEALTH_DEGRADED, HEALTH_REGRESSED, INCONCLUSIVE
    score_delta: float
    changed_checks: tuple[dict[str, str], ...]
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparison_id": self.comparison_id,
            "report_id_a": self.report_id_a,
            "report_id_b": self.report_id_b,
            "trend_status": self.trend_status,
            "score_delta": self.score_delta,
            "changed_checks": list(self.changed_checks),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class IncidentRecord:
    """Structured incident record generated from health check failures."""

    incident_id: str
    health_report_id: str
    deployment_id: str
    release_id: str
    component: str
    severity: str  # INFO, LOW, MEDIUM, HIGH, CRITICAL
    category: str
    detected_condition: str
    evidence: str
    status: str
    created_at: str
    provenance: ObservabilityProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "health_report_id": self.health_report_id,
            "deployment_id": self.deployment_id,
            "release_id": self.release_id,
            "component": self.component,
            "severity": self.severity,
            "category": self.category,
            "detected_condition": self.detected_condition,
            "evidence": self.evidence,
            "status": self.status,
            "created_at": self.created_at,
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True)
class IncidentReview:
    """Human review decision on an incident."""

    review_id: str
    incident_id: str
    reviewed_by: str
    reviewed_at: str
    action: str  # ACKNOWLEDGE, APPROVE_RECOVERY, REJECT_RECOVERY, DEFER_RECOVERY
    notes: str | None
    review_hash: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "review_id": self.review_id,
            "incident_id": self.incident_id,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at,
            "action": self.action,
            "notes": self.notes,
            "review_hash": self.review_hash,
        }


@dataclass(frozen=True)
class RecoveryRecommendation:
    """Recommended recovery action generated for an incident (Non-Autonomous)."""

    recommendation_id: str
    incident_id: str
    recommended_action: str
    reason: str
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    provenance: ObservabilityProvenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "incident_id": self.incident_id,
            "recommended_action": self.recommended_action,
            "reason": self.reason,
            "risk_level": self.risk_level,
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True)
class RecoveryOperation:
    """Explicit human-approved recovery execution record."""

    recovery_id: str
    incident_id: str
    approved_by: str
    approved_at: str
    action: str
    reason: str
    execution_status: str  # RECOVERY_EXECUTING, RECOVERY_VERIFIED, RECOVERY_FAILED
    verification_status: str  # PENDING, VERIFIED, FAILED
    audit_reference: str
    idempotency_key: str

    def to_dict(self) -> dict[str, str]:
        return {
            "recovery_id": self.recovery_id,
            "incident_id": self.incident_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "action": self.action,
            "reason": self.reason,
            "execution_status": self.execution_status,
            "verification_status": self.verification_status,
            "audit_reference": self.audit_reference,
            "idempotency_key": self.idempotency_key,
        }


def compute_recovery_idempotency_key(incident_id: str, action: str) -> str:
    """Compute deterministic idempotency key for recovery operations."""
    payload = f"{incident_id}:{action}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ProductionObservabilityService:
    """Pure domain capability for Phase 26 Production Observability."""

    def generate_health_report(
        self,
        deployment_id: str,
        release_id: str,
        active_version: str,
        checks: Sequence[HealthCheckItem],
        *,
        created_by: str,
        provenance: ObservabilityProvenance | None = None,
    ) -> RuntimeHealthReport:
        """Generate an immutable runtime health observation report."""
        now_str = datetime.now(UTC).isoformat()
        report_id = f"hlth-{uuid4()}"

        # Calculate overall score and status
        total_checks = len(checks)
        if total_checks == 0:
            overall_status = "HEALTHY"
            health_score = 1.0
        else:
            healthy_count = sum(1 for c in checks if c.status == "HEALTHY")
            degraded_count = sum(1 for c in checks if c.status == "DEGRADED")
            unhealthy_count = sum(1 for c in checks if c.status in ("UNHEALTHY", "BLOCKED"))

            health_score = round(healthy_count / total_checks, 4)
            if unhealthy_count > 0:
                overall_status = "UNHEALTHY"
            elif degraded_count > 0:
                overall_status = "DEGRADED"
            else:
                overall_status = "HEALTHY"

        base_prov = provenance or ObservabilityProvenance(
            source_request_id=None,
            source_gap_id=None,
            source_record_id=None,
            candidate_id=None,
            operation_id=None,
            artifact_id=None,
            evaluation_id=None,
            comparison_id=None,
            review_id=None,
            release_id=release_id,
            promotion_operation_id=None,
            deployment_id=deployment_id,
            health_report_id=report_id,
            health_check_id=None,
            incident_id=None,
            recovery_id=None,
        )

        final_prov = ObservabilityProvenance(
            source_request_id=base_prov.source_request_id,
            source_gap_id=base_prov.source_gap_id,
            source_record_id=base_prov.source_record_id,
            candidate_id=base_prov.candidate_id,
            operation_id=base_prov.operation_id,
            artifact_id=base_prov.artifact_id,
            evaluation_id=base_prov.evaluation_id,
            comparison_id=base_prov.comparison_id,
            review_id=base_prov.review_id,
            release_id=release_id,
            promotion_operation_id=base_prov.promotion_operation_id,
            deployment_id=deployment_id,
            health_report_id=report_id,
            health_check_id=None,
            incident_id=base_prov.incident_id,
            recovery_id=base_prov.recovery_id,
        )

        return RuntimeHealthReport(
            health_report_id=report_id,
            deployment_id=deployment_id,
            release_id=release_id,
            active_version=active_version,
            overall_status=overall_status,
            health_score=health_score,
            checks=tuple(checks),
            created_at=now_str,
            provenance=final_prov,
        )

    def compare_health_reports(
        self,
        report_a: RuntimeHealthReport,
        report_b: RuntimeHealthReport,
    ) -> HealthTrendComparison:
        """Compare two historical health reports deterministically."""
        comp_id = f"cmp-hlth-{uuid4()}"
        now_str = datetime.now(UTC).isoformat()
        score_delta = round(report_b.health_score - report_a.health_score, 4)

        if score_delta > 0.05:
            trend = "HEALTH_IMPROVED"
        elif score_delta < -0.1:
            trend = "HEALTH_REGRESSED"
        elif score_delta < 0.0:
            trend = "HEALTH_DEGRADED"
        else:
            trend = "HEALTH_STABLE"

        changed_checks: list[dict[str, str]] = []
        checks_a_map = {c.check_id: c for c in report_a.checks}
        for cb in report_b.checks:
            ca = checks_a_map.get(cb.check_id)
            if ca and ca.status != cb.status:
                changed_checks.append({
                    "check_id": cb.check_id,
                    "component": cb.component,
                    "previous_status": ca.status,
                    "current_status": cb.status,
                })

        return HealthTrendComparison(
            comparison_id=comp_id,
            report_id_a=report_a.health_report_id,
            report_id_b=report_b.health_report_id,
            trend_status=trend,
            score_delta=score_delta,
            changed_checks=tuple(changed_checks),
            created_at=now_str,
        )

    def detect_incidents(
        self,
        report: RuntimeHealthReport,
    ) -> tuple[IncidentRecord, ...]:
        """Convert failing health check items into structured incident records."""
        incidents: list[IncidentRecord] = []
        now_str = datetime.now(UTC).isoformat()

        for check in report.checks:
            if check.status in ("UNHEALTHY", "DEGRADED", "BLOCKED"):
                inc_id = f"inc-{uuid4()}"
                inc_prov = ObservabilityProvenance(
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
                    deployment_id=report.deployment_id,
                    health_report_id=report.health_report_id,
                    health_check_id=check.check_id,
                    incident_id=inc_id,
                    recovery_id=None,
                )
                incidents.append(
                    IncidentRecord(
                        incident_id=inc_id,
                        health_report_id=report.health_report_id,
                        deployment_id=report.deployment_id,
                        release_id=report.release_id,
                        component=check.component,
                        severity=check.severity,
                        category=check.category,
                        detected_condition=f"Check '{check.check_id}' reported '{check.status}'",
                        evidence=check.evidence,
                        status=INCIDENT_STAGE_DETECTED,
                        created_at=now_str,
                        provenance=inc_prov,
                    )
                )

        return tuple(incidents)

    def generate_recovery_recommendations(
        self,
        incident: IncidentRecord,
    ) -> RecoveryRecommendation:
        """Determine non-destructive recovery recommendation for an incident (NON-AUTONOMOUS)."""
        rec_id = f"rec-{uuid4()}"
        if incident.category == "SECURITY":
            rec_action = "INSPECT_SECURITY_ADMIN_BOUNDARY"
            reason = "Security check failure detected; requires manual security audit."
            risk_level = "CRITICAL"
        elif incident.category == "DATABASE_SAFETY":
            rec_action = "VERIFY_DATABASE_CONNECTIVITY"
            reason = "Database health failure detected; check connection pool and backups."
            risk_level = "HIGH"
        elif incident.category == "RELEASE_INTEGRITY":
            rec_action = "ROLLBACK_DEPLOYMENT"
            reason = "Active release version mismatch; deployment rollback recommended."
            risk_level = "HIGH"
        else:
            rec_action = "INSPECT_COMPONENT_HEALTH"
            reason = f"Component '{incident.component}' health degradation detected."
            risk_level = "MEDIUM"

        rec_prov = ObservabilityProvenance(
            source_request_id=incident.provenance.source_request_id,
            source_gap_id=incident.provenance.source_gap_id,
            source_record_id=incident.provenance.source_record_id,
            candidate_id=incident.provenance.candidate_id,
            operation_id=incident.provenance.operation_id,
            artifact_id=incident.provenance.artifact_id,
            evaluation_id=incident.provenance.evaluation_id,
            comparison_id=incident.provenance.comparison_id,
            review_id=incident.provenance.review_id,
            release_id=incident.release_id,
            promotion_operation_id=incident.provenance.promotion_operation_id,
            deployment_id=incident.deployment_id,
            health_report_id=incident.health_report_id,
            health_check_id=incident.provenance.health_check_id,
            incident_id=incident.incident_id,
            recovery_id=None,
        )

        return RecoveryRecommendation(
            recommendation_id=rec_id,
            incident_id=incident.incident_id,
            recommended_action=rec_action,
            reason=reason,
            risk_level=risk_level,
            provenance=rec_prov,
        )

    def process_incident_acknowledgement(
        self,
        incident: IncidentRecord,
        *,
        acknowledged_by: str,
        notes: str | None = None,
    ) -> tuple[IncidentRecord, IncidentReview]:
        """Acknowledge an incident (Human Admin Only)."""
        if not acknowledged_by or not acknowledged_by.strip():
            raise RecoveryApprovalRequiredError("Explicit human admin identity required to acknowledge incident.")

        if incident.status != INCIDENT_STAGE_DETECTED:
            raise InvalidIncidentTransitionError(f"Cannot acknowledge incident in status '{incident.status}'. Expected 'INCIDENT_DETECTED'.")

        now_str = datetime.now(UTC).isoformat()
        rev_id = f"rev-inc-{uuid4()}"
        rev_hash = hashlib.sha256(f"{incident.incident_id}:{acknowledged_by}:ACKNOWLEDGE".encode("utf-8")).hexdigest()

        updated_inc = IncidentRecord(
            incident_id=incident.incident_id,
            health_report_id=incident.health_report_id,
            deployment_id=incident.deployment_id,
            release_id=incident.release_id,
            component=incident.component,
            severity=incident.severity,
            category=incident.category,
            detected_condition=incident.detected_condition,
            evidence=incident.evidence,
            status=INCIDENT_STAGE_ACKNOWLEDGED,
            created_at=incident.created_at,
            provenance=incident.provenance,
        )

        review = IncidentReview(
            review_id=rev_id,
            incident_id=incident.incident_id,
            reviewed_by=acknowledged_by,
            reviewed_at=now_str,
            action="ACKNOWLEDGE",
            notes=notes,
            review_hash=rev_hash,
        )

        return updated_inc, review

    def process_recovery_approval(
        self,
        incident: IncidentRecord,
        decision: str,
        *,
        approved_by: str,
        notes: str | None = None,
    ) -> tuple[IncidentRecord, IncidentReview]:
        """Process explicit human admin recovery decision."""
        if not approved_by or not approved_by.strip():
            raise RecoveryApprovalRequiredError("Explicit human admin identity required for recovery decision.")

        valid_source_statuses = (
            INCIDENT_STAGE_DETECTED,
            INCIDENT_STAGE_ACKNOWLEDGED,
            INCIDENT_STAGE_INVESTIGATING,
            INCIDENT_STAGE_RECOMMENDED,
            INCIDENT_STAGE_PENDING_HUMAN,
        )
        if incident.status not in valid_source_statuses:
            raise InvalidIncidentTransitionError(f"Cannot process recovery decision for incident in status '{incident.status}'.")

        raw_decision = decision.upper()
        if raw_decision in ("APPROVED", INCIDENT_STAGE_APPROVED):
            target_status = INCIDENT_STAGE_APPROVED
        elif raw_decision in ("REJECTED", INCIDENT_STAGE_REJECTED):
            target_status = INCIDENT_STAGE_REJECTED
        elif raw_decision in ("DEFERRED", INCIDENT_STAGE_DEFERRED):
            target_status = INCIDENT_STAGE_DEFERRED
        else:
            raise InvalidIncidentTransitionError(f"Invalid recovery decision '{decision}'. Must be APPROVED, REJECTED, or DEFERRED.")

        now_str = datetime.now(UTC).isoformat()
        rev_id = f"rev-rec-{uuid4()}"
        rev_hash = hashlib.sha256(f"{incident.incident_id}:{approved_by}:{target_status}".encode("utf-8")).hexdigest()

        updated_inc = IncidentRecord(
            incident_id=incident.incident_id,
            health_report_id=incident.health_report_id,
            deployment_id=incident.deployment_id,
            release_id=incident.release_id,
            component=incident.component,
            severity=incident.severity,
            category=incident.category,
            detected_condition=incident.detected_condition,
            evidence=incident.evidence,
            status=target_status,
            created_at=incident.created_at,
            provenance=incident.provenance,
        )

        review = IncidentReview(
            review_id=rev_id,
            incident_id=incident.incident_id,
            reviewed_by=approved_by,
            reviewed_at=now_str,
            action=target_status,
            notes=notes,
            review_hash=rev_hash,
        )

        return updated_inc, review

    def execute_recovery(
        self,
        incident: IncidentRecord,
        action: str,
        *,
        approved_by: str,
        reason: str,
    ) -> tuple[IncidentRecord, RecoveryOperation]:
        """Execute explicit human-approved recovery operation."""
        if not approved_by or not approved_by.strip():
            raise RecoveryApprovalRequiredError("Explicit human admin identity required to execute recovery.")

        if incident.status != INCIDENT_STAGE_APPROVED:
            raise InvalidIncidentTransitionError(f"Cannot execute recovery for incident in status '{incident.status}'. Expected 'RECOVERY_APPROVED'.")

        now_str = datetime.now(UTC).isoformat()
        rec_op_id = f"op-rec-{uuid4()}"
        idemp_key = compute_recovery_idempotency_key(incident.incident_id, action)

        rec_prov = ObservabilityProvenance(
            source_request_id=incident.provenance.source_request_id,
            source_gap_id=incident.provenance.source_gap_id,
            source_record_id=incident.provenance.source_record_id,
            candidate_id=incident.provenance.candidate_id,
            operation_id=incident.provenance.operation_id,
            artifact_id=incident.provenance.artifact_id,
            evaluation_id=incident.provenance.evaluation_id,
            comparison_id=incident.provenance.comparison_id,
            review_id=incident.provenance.review_id,
            release_id=incident.release_id,
            promotion_operation_id=incident.provenance.promotion_operation_id,
            deployment_id=incident.deployment_id,
            health_report_id=incident.health_report_id,
            health_check_id=incident.provenance.health_check_id,
            incident_id=incident.incident_id,
            recovery_id=rec_op_id,
        )

        updated_inc = IncidentRecord(
            incident_id=incident.incident_id,
            health_report_id=incident.health_report_id,
            deployment_id=incident.deployment_id,
            release_id=incident.release_id,
            component=incident.component,
            severity=incident.severity,
            category=incident.category,
            detected_condition=incident.detected_condition,
            evidence=incident.evidence,
            status=INCIDENT_STAGE_VERIFIED,
            created_at=incident.created_at,
            provenance=rec_prov,
        )

        rec_op = RecoveryOperation(
            recovery_id=rec_op_id,
            incident_id=incident.incident_id,
            approved_by=approved_by,
            approved_at=now_str,
            action=action,
            reason=reason,
            execution_status=INCIDENT_STAGE_VERIFIED,
            verification_status="VERIFIED",
            audit_reference=f"audit-rec-{rec_op_id}",
            idempotency_key=idemp_key,
        )

        return updated_inc, rec_op
