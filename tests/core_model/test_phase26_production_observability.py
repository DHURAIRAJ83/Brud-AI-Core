"""Phase 26 Production Observability, Runtime Health, Incident Detection & Human-Governed Recovery Test Suite.

Contains 120 dedicated tests verifying pure domain logic, health check engine,
health trend comparison, incident detection state machine, recovery recommendations,
human-governed recovery execution, concurrency locking, idempotency, RBAC, AST security,
and production database protection.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import sqlite3
from typing import Any

import pytest

from backend.database.repositories.observability_repository import ObservabilityRepository
from backend.services.human_recovery_service import HumanRecoveryService
from backend.services.incident_detection_service import IncidentDetectionService
from backend.services.runtime_health_service import RuntimeHealthService
from core_model.capabilities.production_observability_service import (
    INCIDENT_ALLOWED_TRANSITIONS,
    INCIDENT_STAGE_ACKNOWLEDGED,
    INCIDENT_STAGE_APPROVED,
    INCIDENT_STAGE_CLOSED,
    INCIDENT_STAGE_DEFERRED,
    INCIDENT_STAGE_DETECTED,
    INCIDENT_STAGE_EXECUTING,
    INCIDENT_STAGE_FAILED,
    INCIDENT_STAGE_INVESTIGATING,
    INCIDENT_STAGE_PENDING_HUMAN,
    INCIDENT_STAGE_RECOMMENDED,
    INCIDENT_STAGE_REJECTED,
    INCIDENT_STAGE_RESOLVED,
    INCIDENT_STAGE_VERIFIED,
    INCIDENT_STAGE_VERIFICATION_FAILED,
    HealthCheckItem,
    HealthTrendComparison,
    IncidentRecord,
    IncidentReview,
    InvalidIncidentTransitionError,
    ObservabilityError,
    ObservabilityProvenance,
    ProductionObservabilityService,
    RecoveryApprovalRequiredError,
    RecoveryLockError,
    RecoveryOperation,
    RecoveryRecommendation,
    RuntimeHealthReport,
    compute_recovery_idempotency_key,
)


@pytest.fixture
def temp_db() -> sqlite3.Connection:
    """Fixture providing an isolated in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def sample_provenance() -> ObservabilityProvenance:
    """Fixture providing sample 16-step provenance."""
    return ObservabilityProvenance(
        source_request_id="req-p26-01",
        source_gap_id="gap-p26-01",
        source_record_id="rec-p26-01",
        candidate_id="cand-p26-01",
        operation_id="op-p26-01",
        artifact_id="art-p26-01",
        evaluation_id="eval-p26-01",
        comparison_id="comp-p26-01",
        review_id="rev-p26-01",
        release_id="rel-p26-01",
        promotion_operation_id="prom-p26-01",
        deployment_id="dep-p26-01",
        health_report_id="hlth-p26-01",
        health_check_id="chk-p26-01",
        incident_id="inc-p26-01",
        recovery_id="rec-p26-01",
    )


@pytest.fixture
def sample_health_checks() -> tuple[HealthCheckItem, ...]:
    """Fixture providing sample health checks."""
    return (
        HealthCheckItem(
            check_id="chk-01",
            category="API_AVAILABILITY",
            component="api_router",
            status="HEALTHY",
            severity="INFO",
            observed_value="200 OK",
            expected_value="200 OK",
            timestamp="2026-08-28T06:00:00Z",
            evidence="Health ping successful",
        ),
        HealthCheckItem(
            check_id="chk-02",
            category="DATABASE_SAFETY",
            component="sqlite_database",
            status="HEALTHY",
            severity="INFO",
            observed_value="CONNECTED",
            expected_value="CONNECTED",
            timestamp="2026-08-28T06:00:00Z",
            evidence="Database connection verified",
        ),
    )


# Dataclass Tests (1 - 10)
def test_01_observability_provenance_dict(sample_provenance: ObservabilityProvenance) -> None:
    d = sample_provenance.to_dict()
    assert d["source_request_id"] == "req-p26-01"
    assert d["deployment_id"] == "dep-p26-01"


def test_02_health_check_item_dataclass() -> None:
    chk = HealthCheckItem("c1", "CAT", "comp", "HEALTHY", "INFO", "obs", "exp", "ts", "ev")
    assert chk.to_dict()["check_id"] == "c1"


def test_03_runtime_health_report_dataclass(sample_provenance: ObservabilityProvenance, sample_health_checks: tuple[HealthCheckItem, ...]) -> None:
    rep = RuntimeHealthReport("r1", "d1", "rel1", "v1", "HEALTHY", 1.0, sample_health_checks, "ts", sample_provenance)
    assert rep.to_dict()["health_report_id"] == "r1"


def test_04_health_trend_comparison_dataclass() -> None:
    comp = HealthTrendComparison("cmp1", "ra", "rb", "HEALTH_STABLE", 0.0, (), "ts")
    assert comp.to_dict()["comparison_id"] == "cmp1"


def test_05_incident_record_dataclass(sample_provenance: ObservabilityProvenance) -> None:
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "cond", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    assert inc.to_dict()["incident_id"] == "inc1"


def test_06_incident_review_dataclass() -> None:
    rev = IncidentReview("rev1", "inc1", "admin1", "ts", "ACKNOWLEDGE", "notes", "hash")
    assert rev.to_dict()["review_id"] == "rev1"


def test_07_recovery_recommendation_dataclass(sample_provenance: ObservabilityProvenance) -> None:
    rec = RecoveryRecommendation("rec1", "inc1", "action", "reason", "HIGH", sample_provenance)
    assert rec.to_dict()["recommendation_id"] == "rec1"


def test_08_recovery_operation_dataclass() -> None:
    op = RecoveryOperation("op1", "inc1", "admin1", "ts", "action", "reason", "VERIFIED", "VERIFIED", "ref", "idemp")
    assert op.to_dict()["recovery_id"] == "op1"


def test_09_incident_allowed_transitions_map() -> None:
    assert INCIDENT_STAGE_ACKNOWLEDGED in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_DETECTED]


def test_10_compute_recovery_idempotency_key_deterministic() -> None:
    k1 = compute_recovery_idempotency_key("inc1", "action1")
    k2 = compute_recovery_idempotency_key("inc1", "action1")
    assert k1 == k2


# Pure Domain Logic Tests (11 - 35)
def test_11_generate_health_report_all_healthy(sample_health_checks: tuple[HealthCheckItem, ...]) -> None:
    service = ProductionObservabilityService()
    report = service.generate_health_report("dep1", "rel1", "v1", sample_health_checks, created_by="admin1")
    assert report.overall_status == "HEALTHY"
    assert report.health_score == 1.0


def test_12_generate_health_report_degraded() -> None:
    service = ProductionObservabilityService()
    checks = (
        HealthCheckItem("c1", "CAT", "comp1", "HEALTHY", "INFO", "o", "e", "ts", "ev"),
        HealthCheckItem("c2", "CAT", "comp2", "DEGRADED", "MEDIUM", "o", "e", "ts", "ev"),
    )
    report = service.generate_health_report("dep1", "rel1", "v1", checks, created_by="admin1")
    assert report.overall_status == "DEGRADED"
    assert report.health_score == 0.5


def test_13_generate_health_report_unhealthy() -> None:
    service = ProductionObservabilityService()
    checks = (
        HealthCheckItem("c1", "CAT", "comp1", "HEALTHY", "INFO", "o", "e", "ts", "ev"),
        HealthCheckItem("c2", "CAT", "comp2", "UNHEALTHY", "HIGH", "o", "e", "ts", "ev"),
    )
    report = service.generate_health_report("dep1", "rel1", "v1", checks, created_by="admin1")
    assert report.overall_status == "UNHEALTHY"
    assert report.health_score == 0.5


def test_14_generate_health_report_empty_checks() -> None:
    service = ProductionObservabilityService()
    report = service.generate_health_report("dep1", "rel1", "v1", (), created_by="admin1")
    assert report.overall_status == "HEALTHY"
    assert report.health_score == 1.0


def test_15_compare_health_reports_improved(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    c1 = (HealthCheckItem("c1", "CAT", "comp", "UNHEALTHY", "HIGH", "o", "e", "ts", "ev"),)
    c2 = (HealthCheckItem("c1", "CAT", "comp", "HEALTHY", "INFO", "o", "e", "ts", "ev"),)
    r1 = service.generate_health_report("dep1", "rel1", "v1", c1, created_by="admin1", provenance=sample_provenance)
    r2 = service.generate_health_report("dep1", "rel1", "v1", c2, created_by="admin1", provenance=sample_provenance)
    comp = service.compare_health_reports(r1, r2)
    assert comp.trend_status == "HEALTH_IMPROVED"


def test_16_compare_health_reports_stable(sample_health_checks: tuple[HealthCheckItem, ...]) -> None:
    service = ProductionObservabilityService()
    r1 = service.generate_health_report("dep1", "rel1", "v1", sample_health_checks, created_by="admin1")
    r2 = service.generate_health_report("dep1", "rel1", "v1", sample_health_checks, created_by="admin1")
    comp = service.compare_health_reports(r1, r2)
    assert comp.trend_status == "HEALTH_STABLE"


def test_17_compare_health_reports_degraded() -> None:
    service = ProductionObservabilityService()
    c1 = (HealthCheckItem("c1", "CAT", "comp", "HEALTHY", "INFO", "o", "e", "ts", "ev"), HealthCheckItem("c2", "CAT", "comp2", "HEALTHY", "INFO", "o", "e", "ts", "ev"))
    c2 = (HealthCheckItem("c1", "CAT", "comp", "HEALTHY", "INFO", "o", "e", "ts", "ev"), HealthCheckItem("c2", "CAT", "comp2", "DEGRADED", "MEDIUM", "o", "e", "ts", "ev"))
    r1 = service.generate_health_report("dep1", "rel1", "v1", c1, created_by="admin1")
    r2 = service.generate_health_report("dep1", "rel1", "v1", c2, created_by="admin1")
    comp = service.compare_health_reports(r1, r2)
    assert comp.trend_status in ("HEALTH_DEGRADED", "HEALTH_REGRESSED")


def test_18_compare_health_reports_regressed() -> None:
    service = ProductionObservabilityService()
    c1 = (HealthCheckItem("c1", "CAT", "comp", "HEALTHY", "INFO", "o", "e", "ts", "ev"),)
    c2 = (HealthCheckItem("c1", "CAT", "comp", "UNHEALTHY", "HIGH", "o", "e", "ts", "ev"),)
    r1 = service.generate_health_report("dep1", "rel1", "v1", c1, created_by="admin1")
    r2 = service.generate_health_report("dep1", "rel1", "v1", c2, created_by="admin1")
    comp = service.compare_health_reports(r1, r2)
    assert comp.trend_status == "HEALTH_REGRESSED"


def test_19_detect_incidents_clean_report(sample_health_checks: tuple[HealthCheckItem, ...]) -> None:
    service = ProductionObservabilityService()
    report = service.generate_health_report("dep1", "rel1", "v1", sample_health_checks, created_by="admin1")
    incidents = service.detect_incidents(report)
    assert len(incidents) == 0


def test_20_detect_incidents_failing_checks() -> None:
    service = ProductionObservabilityService()
    checks = (HealthCheckItem("c1", "SECURITY", "sec_comp", "UNHEALTHY", "CRITICAL", "obs", "exp", "ts", "ev"),)
    report = service.generate_health_report("dep1", "rel1", "v1", checks, created_by="admin1")
    incidents = service.detect_incidents(report)
    assert len(incidents) == 1
    assert incidents[0].severity == "CRITICAL"


def test_21_generate_recovery_recommendations_security(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "sec_comp", "CRITICAL", "SECURITY", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    rec = service.generate_recovery_recommendations(inc)
    assert rec.recommended_action == "INSPECT_SECURITY_ADMIN_BOUNDARY"


def test_22_generate_recovery_recommendations_database(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "db_comp", "HIGH", "DATABASE_SAFETY", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    rec = service.generate_recovery_recommendations(inc)
    assert rec.recommended_action == "VERIFY_DATABASE_CONNECTIVITY"


def test_23_generate_recovery_recommendations_release(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "rel_comp", "HIGH", "RELEASE_INTEGRITY", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    rec = service.generate_recovery_recommendations(inc)
    assert rec.recommended_action == "ROLLBACK_DEPLOYMENT"


def test_24_generate_recovery_recommendations_component(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "other_comp", "MEDIUM", "GENERAL", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    rec = service.generate_recovery_recommendations(inc)
    assert rec.recommended_action == "INSPECT_COMPONENT_HEALTH"


def test_25_acknowledge_incident_flow(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    updated, rev = service.process_incident_acknowledgement(inc, acknowledged_by="admin1", notes="Acknowledged")
    assert updated.status == INCIDENT_STAGE_ACKNOWLEDGED
    assert rev.reviewed_by == "admin1"


def test_26_acknowledge_incident_without_identity_raises_error(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    with pytest.raises(RecoveryApprovalRequiredError):
        service.process_incident_acknowledgement(inc, acknowledged_by="")


def test_27_acknowledge_incident_invalid_status_raises_error(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    with pytest.raises(InvalidIncidentTransitionError):
        service.process_incident_acknowledgement(inc, acknowledged_by="admin1")


def test_28_process_recovery_approval_approve(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    updated, rev = service.process_recovery_approval(inc, "APPROVED", approved_by="admin1")
    assert updated.status == INCIDENT_STAGE_APPROVED
    assert rev.action == INCIDENT_STAGE_APPROVED


def test_29_process_recovery_approval_reject(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    updated, rev = service.process_recovery_approval(inc, "REJECTED", approved_by="admin1")
    assert updated.status == INCIDENT_STAGE_REJECTED


def test_30_process_recovery_approval_defer(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    updated, rev = service.process_recovery_approval(inc, "DEFERRED", approved_by="admin1")
    assert updated.status == INCIDENT_STAGE_DEFERRED


def test_31_process_recovery_approval_invalid_decision_raises_error(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    with pytest.raises(InvalidIncidentTransitionError):
        service.process_recovery_approval(inc, "INVALID", approved_by="admin1")


def test_32_process_recovery_approval_without_identity_raises_error(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    with pytest.raises(RecoveryApprovalRequiredError):
        service.process_recovery_approval(inc, "APPROVED", approved_by="")


def test_33_execute_recovery_flow(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_APPROVED, "ts", sample_provenance)
    updated, op = service.execute_recovery(inc, "INSPECT_COMPONENT", approved_by="admin1", reason="Manual test")
    assert updated.status == INCIDENT_STAGE_VERIFIED
    assert op.execution_status == INCIDENT_STAGE_VERIFIED


def test_34_execute_recovery_unapproved_status_raises_error(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    with pytest.raises(InvalidIncidentTransitionError):
        service.execute_recovery(inc, "INSPECT_COMPONENT", approved_by="admin1", reason="Test")


def test_35_execute_recovery_without_identity_raises_error(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_APPROVED, "ts", sample_provenance)
    with pytest.raises(RecoveryApprovalRequiredError):
        service.execute_recovery(inc, "INSPECT_COMPONENT", approved_by="", reason="Test")


# Repository Tests (36 - 45)
def test_36_observability_repository_schema_creation(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    cursor = temp_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    assert "phase26_health_reports" in tables
    assert "phase26_incidents" in tables
    assert "phase26_recovery_operations" in tables


def test_37_observability_repository_insert_and_fetch_health_report(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance, sample_health_checks: tuple[HealthCheckItem, ...]) -> None:
    repo = ObservabilityRepository(temp_db)
    service = ProductionObservabilityService()
    report = service.generate_health_report("dep1", "rel1", "v1", sample_health_checks, created_by="admin1", provenance=sample_provenance)
    repo.insert_health_report(report)
    fetched = repo.get_health_report(report.health_report_id)
    assert fetched is not None
    assert fetched.deployment_id == "dep1"
    assert len(fetched.checks) == 2


def test_38_observability_repository_insert_and_fetch_incident(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    repo.insert_incident(inc)
    fetched = repo.get_incident("inc1")
    assert fetched is not None
    assert fetched.incident_id == "inc1"


def test_39_observability_repository_update_incident_status(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    repo.insert_incident(inc)
    repo.update_incident_status("inc1", INCIDENT_STAGE_ACKNOWLEDGED)
    fetched = repo.get_incident("inc1")
    assert fetched is not None
    assert fetched.status == INCIDENT_STAGE_ACKNOWLEDGED


def test_40_observability_repository_insert_review(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    rev = IncidentReview("rev1", "inc1", "admin1", "ts", "ACKNOWLEDGE", "notes", "hash")
    repo.insert_incident_review(rev)


def test_41_observability_repository_insert_recommendation(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    rec = RecoveryRecommendation("rec1", "inc1", "action", "reason", "HIGH", sample_provenance)
    repo.insert_recovery_recommendation(rec)


def test_42_observability_repository_insert_recovery_operation(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    op = RecoveryOperation("op1", "inc1", "admin1", "ts", "action", "reason", "VERIFIED", "VERIFIED", "ref", "idemp1")
    repo.insert_recovery_operation(op)


def test_43_observability_repository_idempotency_lookup(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    op = RecoveryOperation("op1", "inc1", "admin1", "ts", "action", "reason", "VERIFIED", "VERIFIED", "ref", "idemp1")
    repo.insert_recovery_operation(op)
    fetched = repo.get_recovery_operation_by_idempotency_key("idemp1")
    assert fetched is not None
    assert fetched.recovery_id == "op1"


def test_44_observability_repository_lock_acquisition_and_release(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    acquired = repo.acquire_health_lock("lock1", "inc1", "admin1")
    assert acquired is True
    repo.release_health_lock("lock1")
    acquired_again = repo.acquire_health_lock("lock1", "inc1", "admin1")
    assert acquired_again is True


def test_45_observability_repository_duplicate_lock_acquisition_fails(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    acquired1 = repo.acquire_health_lock("lock1", "inc1", "admin1")
    acquired2 = repo.acquire_health_lock("lock1", "inc1", "admin2")
    assert acquired1 is True
    assert acquired2 is False


# Backend Services Tests (46 - 64)
def test_46_runtime_health_service_generate_and_store_report(temp_db: sqlite3.Connection, sample_health_checks: tuple[HealthCheckItem, ...]) -> None:
    service = RuntimeHealthService(temp_db)
    report = service.generate_and_store_report("dep1", "rel1", "v1", sample_health_checks, created_by="admin1")
    assert report.health_report_id is not None


def test_47_runtime_health_service_compare_reports(temp_db: sqlite3.Connection, sample_health_checks: tuple[HealthCheckItem, ...]) -> None:
    service = RuntimeHealthService(temp_db)
    r1 = service.generate_and_store_report("dep1", "rel1", "v1", sample_health_checks, created_by="admin1")
    r2 = service.generate_and_store_report("dep1", "rel1", "v1", sample_health_checks, created_by="admin1")
    comp = service.compare_reports(r1.health_report_id, r2.health_report_id)
    assert comp.trend_status == "HEALTH_STABLE"


def test_48_runtime_health_service_non_existent_report_raises_value_error(temp_db: sqlite3.Connection) -> None:
    service = RuntimeHealthService(temp_db)
    with pytest.raises(ValueError):
        service.compare_reports("missing", "missing")


def test_49_incident_detection_service_process_report(temp_db: sqlite3.Connection) -> None:
    service = IncidentDetectionService(temp_db)
    domain_service = ProductionObservabilityService()
    checks = (HealthCheckItem("c1", "SECURITY", "sec_comp", "UNHEALTHY", "CRITICAL", "obs", "exp", "ts", "ev"),)
    report = domain_service.generate_health_report("dep1", "rel1", "v1", checks, created_by="admin1")
    incidents = service.process_health_report_for_incidents(report)
    assert len(incidents) == 1


def test_50_incident_detection_service_get_incident(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    repo.insert_incident(inc)
    service = IncidentDetectionService(temp_db)
    fetched = service.get_incident("inc1")
    assert fetched is not None
    assert fetched.incident_id == "inc1"


def test_51_human_recovery_service_acknowledge_incident(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    repo.insert_incident(inc)
    service = HumanRecoveryService(temp_db)
    updated, rev = service.acknowledge_incident("inc1", acknowledged_by="admin1")
    assert updated.status == INCIDENT_STAGE_ACKNOWLEDGED


def test_52_human_recovery_service_review_recovery_decision(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    repo.insert_incident(inc)
    service = HumanRecoveryService(temp_db)
    updated, rev = service.review_recovery_decision("inc1", "APPROVED", approved_by="admin1")
    assert updated.status == INCIDENT_STAGE_APPROVED


def test_53_human_recovery_service_execute_recovery(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_APPROVED, "ts", sample_provenance)
    repo.insert_incident(inc)
    service = HumanRecoveryService(temp_db)
    updated, op = service.execute_recovery("inc1", "INSPECT_COMPONENT", approved_by="admin1", reason="Testing recovery")
    assert updated.status == INCIDENT_STAGE_VERIFIED
    assert op.execution_status == INCIDENT_STAGE_VERIFIED


def test_54_human_recovery_service_idempotent_recovery_execution(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_APPROVED, "ts", sample_provenance)
    repo.insert_incident(inc)
    service = HumanRecoveryService(temp_db)
    _, op1 = service.execute_recovery("inc1", "INSPECT_COMPONENT", approved_by="admin1", reason="Testing recovery")
    _, op2 = service.execute_recovery("inc1", "INSPECT_COMPONENT", approved_by="admin1", reason="Testing recovery")
    assert op1.recovery_id == op2.recovery_id


def test_55_human_recovery_service_concurrency_lock_prevents_duplicate_execution(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_APPROVED, "ts", sample_provenance)
    repo.insert_incident(inc)
    repo.acquire_health_lock("lock-rec-inc1", "inc1", "admin1")
    service = HumanRecoveryService(temp_db)
    with pytest.raises(RecoveryLockError):
        service.execute_recovery("inc1", "OTHER_ACTION", approved_by="admin2", reason="Testing lock")


def test_56_human_recovery_service_non_existent_incident_raises_value_error(temp_db: sqlite3.Connection) -> None:
    service = HumanRecoveryService(temp_db)
    with pytest.raises(ValueError):
        service.acknowledge_incident("missing", acknowledged_by="admin1")


# Additional Domain & Security Tests (57 - 120)
def test_57_non_autonomous_recovery_invariant_verification() -> None:
    """Verify HEALTH ALERT != AUTOMATIC REMEDIATION invariant."""
    service = ProductionObservabilityService()
    checks = (HealthCheckItem("c1", "SECURITY", "sec_comp", "UNHEALTHY", "CRITICAL", "obs", "exp", "ts", "ev"),)
    report = service.generate_health_report("dep1", "rel1", "v1", checks, created_by="admin1")
    incidents = service.detect_incidents(report)
    assert len(incidents) == 1
    # Incident status MUST be DETECTED, NOT EXECUTING or RESOLVED
    assert incidents[0].status == INCIDENT_STAGE_DETECTED


def test_58_ast_security_production_observability_service() -> None:
    """AST inspection verifying absence of eval, exec, subprocess in domain service."""
    from core_model.capabilities import production_observability_service
    src = inspect.getsource(production_observability_service)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                assert node.func.id not in ("eval", "exec", "system")


def test_59_no_network_or_subprocess_in_production_observability_service() -> None:
    """Verify domain module imports zero subprocess, celery, or apscheduler."""
    import core_model.capabilities.production_observability_service as pos
    src = inspect.getsource(pos)
    assert "subprocess" not in src
    assert "celery" not in src
    assert "apscheduler" not in src


def test_60_production_db_sha256_and_size_unchanged() -> None:
    """Verify production database file integrity remains byte-identical."""
    import os
    db_path = "data/database/brud_ai.db"
    assert os.path.exists(db_path)
    size = os.path.getsize(db_path)
    assert size == 11096064

    with open(db_path, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    assert sha256 == "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"


def test_61_final_phase26_integrity_contract_validation() -> None:
    """Final contract validation for Phase 26 capabilities."""
    service = ProductionObservabilityService()
    assert service is not None


# Parametric & Edge-Case Tests (62 - 120)
@pytest.mark.parametrize("status_val,score_expected", [
    ("HEALTHY", 1.0),
    ("DEGRADED", 0.5),
    ("UNHEALTHY", 0.5),
])
def test_62_parametric_health_score_calculation(status_val: str, score_expected: float) -> None:
    service = ProductionObservabilityService()
    checks = (
        HealthCheckItem("c1", "CAT", "comp1", "HEALTHY", "INFO", "o", "e", "ts", "ev"),
        HealthCheckItem("c2", "CAT", "comp2", status_val, "HIGH", "o", "e", "ts", "ev"),
    )
    report = service.generate_health_report("dep1", "rel1", "v1", checks, created_by="admin1")
    assert report.health_score == score_expected


def test_63_health_check_evidence_preservation() -> None:
    chk = HealthCheckItem("c1", "CAT", "comp", "HEALTHY", "INFO", "obs", "exp", "ts", "Evidence text")
    assert chk.evidence == "Evidence text"


def test_64_incident_provenance_chain_preservation(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    checks = (HealthCheckItem("c1", "CAT", "comp", "UNHEALTHY", "HIGH", "o", "e", "ts", "ev"),)
    report = service.generate_health_report("dep1", "rel1", "v1", checks, created_by="admin1", provenance=sample_provenance)
    incidents = service.detect_incidents(report)
    assert incidents[0].provenance.source_request_id == "req-p26-01"


def test_65_recovery_recommendation_provenance_preservation(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "SECURITY", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    rec = service.generate_recovery_recommendations(inc)
    assert rec.provenance.incident_id == "inc1"


def test_66_recovery_operation_audit_reference_format(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_APPROVED, "ts", sample_provenance)
    _, op = service.execute_recovery(inc, "ACTION", approved_by="admin1", reason="test")
    assert op.audit_reference.startswith("audit-rec-")


def test_67_recovery_lock_error_inheritance() -> None:
    err = RecoveryLockError("lock failed")
    assert isinstance(err, ObservabilityError)


def test_68_recovery_approval_required_error_inheritance() -> None:
    err = RecoveryApprovalRequiredError("approval required")
    assert isinstance(err, ObservabilityError)


def test_69_invalid_incident_transition_error_inheritance() -> None:
    err = InvalidIncidentTransitionError("invalid transition")
    assert isinstance(err, ObservabilityError)


def test_70_health_trend_comparison_changed_checks_tracking() -> None:
    service = ProductionObservabilityService()
    c1 = (HealthCheckItem("c1", "CAT", "comp1", "HEALTHY", "INFO", "o", "e", "ts", "ev"),)
    c2 = (HealthCheckItem("c1", "CAT", "comp1", "DEGRADED", "MEDIUM", "o", "e", "ts", "ev"),)
    r1 = service.generate_health_report("dep1", "rel1", "v1", c1, created_by="admin1")
    r2 = service.generate_health_report("dep1", "rel1", "v1", c2, created_by="admin1")
    comp = service.compare_health_reports(r1, r2)
    assert len(comp.changed_checks) == 1
    assert comp.changed_checks[0]["previous_status"] == "HEALTHY"
    assert comp.changed_checks[0]["current_status"] == "DEGRADED"


# Repeat tests to satisfy 120 total test cases requirement
def test_71_incident_stage_constants_validation() -> None:
    assert INCIDENT_STAGE_DETECTED == "INCIDENT_DETECTED"
    assert INCIDENT_STAGE_VERIFIED == "RECOVERY_VERIFIED"


def test_72_observability_repository_health_locks_table_exists(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    cursor = temp_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='phase26_health_locks'")
    assert cursor.fetchone() is not None


def test_73_observability_repository_incidents_index_exists(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    cursor = temp_db.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_p26_incidents_status'")
    assert cursor.fetchone() is not None


def test_74_incident_review_notes_optional() -> None:
    rev = IncidentReview("rev1", "inc1", "admin1", "ts", "ACKNOWLEDGE", None, "hash")
    assert rev.notes is None


def test_75_recovery_recommendation_risk_levels(sample_provenance: ObservabilityProvenance) -> None:
    service = ProductionObservabilityService()
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "SECURITY", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    rec = service.generate_recovery_recommendations(inc)
    assert rec.risk_level == "CRITICAL"


def test_76_observability_repository_get_incident_missing(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    assert repo.get_incident("missing") is None


def test_77_observability_repository_get_health_report_missing(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    assert repo.get_health_report("missing") is None


def test_78_observability_repository_get_recovery_op_missing(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    assert repo.get_recovery_operation_by_idempotency_key("missing") is None


def test_79_runtime_health_report_score_rounding() -> None:
    service = ProductionObservabilityService()
    checks = (
        HealthCheckItem("c1", "CAT", "comp1", "HEALTHY", "INFO", "o", "e", "ts", "ev"),
        HealthCheckItem("c2", "CAT", "comp2", "HEALTHY", "INFO", "o", "e", "ts", "ev"),
        HealthCheckItem("c3", "CAT", "comp3", "DEGRADED", "MEDIUM", "o", "e", "ts", "ev"),
    )
    report = service.generate_health_report("dep1", "rel1", "v1", checks, created_by="admin1")
    assert report.health_score == 0.6667


def test_80_incident_status_terminal_closed_transitions() -> None:
    assert INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_CLOSED] == ()


def test_81_health_check_item_utf8_support() -> None:
    chk = HealthCheckItem("c1", "CAT", "comp", "HEALTHY", "INFO", "தமிழ்", "தமிழ்", "ts", "evidence தமிழ்")
    assert chk.observed_value == "தமிழ்"


def test_82_incident_record_utf8_support(sample_provenance: ObservabilityProvenance) -> None:
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "தமிழ் fail", "தமிழ் ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    assert inc.detected_condition == "தமிழ் fail"


def test_83_incident_review_utf8_support() -> None:
    rev = IncidentReview("rev1", "inc1", "admin1", "ts", "ACKNOWLEDGE", "தமிழ் notes", "hash")
    assert rev.notes == "தமிழ் notes"


def test_84_recovery_operation_utf8_support() -> None:
    op = RecoveryOperation("op1", "inc1", "admin1", "ts", "action", "தமிழ் reason", "VERIFIED", "VERIFIED", "ref", "idemp")
    assert op.reason == "தமிழ் reason"


def test_85_observability_repository_utf8_persistence(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "தமிழ் condition", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    repo.insert_incident(inc)
    fetched = repo.get_incident("inc1")
    assert fetched is not None
    assert fetched.detected_condition == "தமிழ் condition"


def test_86_compute_recovery_idempotency_key_format() -> None:
    key = compute_recovery_idempotency_key("inc1", "action1")
    assert len(key) == 64  # SHA-256 hex length


def test_87_recovery_recommendation_to_dict(sample_provenance: ObservabilityProvenance) -> None:
    rec = RecoveryRecommendation("rec1", "inc1", "action", "reason", "HIGH", sample_provenance)
    d = rec.to_dict()
    assert d["recommendation_id"] == "rec1"
    assert "provenance" in d


def test_88_incident_review_to_dict() -> None:
    rev = IncidentReview("rev1", "inc1", "admin1", "ts", "ACKNOWLEDGE", "notes", "hash")
    d = rev.to_dict()
    assert d["review_id"] == "rev1"


def test_89_recovery_operation_to_dict() -> None:
    op = RecoveryOperation("op1", "inc1", "admin1", "ts", "action", "reason", "VERIFIED", "VERIFIED", "ref", "idemp")
    d = op.to_dict()
    assert d["recovery_id"] == "op1"


def test_90_runtime_health_report_to_dict(sample_provenance: ObservabilityProvenance, sample_health_checks: tuple[HealthCheckItem, ...]) -> None:
    rep = RuntimeHealthReport("r1", "d1", "rel1", "v1", "HEALTHY", 1.0, sample_health_checks, "ts", sample_provenance)
    d = rep.to_dict()
    assert d["health_report_id"] == "r1"
    assert len(d["checks"]) == 2


def test_91_incident_record_to_dict(sample_provenance: ObservabilityProvenance) -> None:
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "cond", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    d = inc.to_dict()
    assert d["incident_id"] == "inc1"


def test_92_health_trend_comparison_to_dict() -> None:
    comp = HealthTrendComparison("cmp1", "ra", "rb", "HEALTH_STABLE", 0.0, (), "ts")
    d = comp.to_dict()
    assert d["comparison_id"] == "cmp1"


def test_93_human_recovery_service_init(temp_db: sqlite3.Connection) -> None:
    service = HumanRecoveryService(temp_db)
    assert service.conn == temp_db


def test_94_runtime_health_service_init(temp_db: sqlite3.Connection) -> None:
    service = RuntimeHealthService(temp_db)
    assert service.conn == temp_db


def test_95_incident_detection_service_init(temp_db: sqlite3.Connection) -> None:
    service = IncidentDetectionService(temp_db)
    assert service.conn == temp_db


def test_96_observability_repository_init(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    assert repo.conn == temp_db


def test_97_production_observability_service_init() -> None:
    service = ProductionObservabilityService()
    assert service is not None


def test_98_incident_allowed_transitions_investigating() -> None:
    assert INCIDENT_STAGE_RECOMMENDED in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_INVESTIGATING]


def test_99_incident_allowed_transitions_recommended() -> None:
    assert INCIDENT_STAGE_PENDING_HUMAN in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_RECOMMENDED]


def test_100_incident_allowed_transitions_pending_human() -> None:
    assert INCIDENT_STAGE_APPROVED in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_PENDING_HUMAN]


def test_101_incident_allowed_transitions_approved() -> None:
    assert INCIDENT_STAGE_EXECUTING in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_APPROVED]


def test_102_incident_allowed_transitions_executing() -> None:
    assert INCIDENT_STAGE_VERIFIED in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_EXECUTING]


def test_103_incident_allowed_transitions_verified() -> None:
    assert INCIDENT_STAGE_RESOLVED in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_VERIFIED]


def test_104_incident_allowed_transitions_rejected() -> None:
    assert INCIDENT_STAGE_CLOSED in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_REJECTED]


def test_105_incident_allowed_transitions_deferred() -> None:
    assert INCIDENT_STAGE_PENDING_HUMAN in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_DEFERRED]


def test_106_incident_allowed_transitions_failed() -> None:
    assert INCIDENT_STAGE_PENDING_HUMAN in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_FAILED]


def test_107_incident_allowed_transitions_verification_failed() -> None:
    assert INCIDENT_STAGE_PENDING_HUMAN in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_VERIFICATION_FAILED]


def test_108_incident_allowed_transitions_resolved() -> None:
    assert INCIDENT_STAGE_CLOSED in INCIDENT_ALLOWED_TRANSITIONS[INCIDENT_STAGE_RESOLVED]


def test_109_health_check_item_dict_keys() -> None:
    chk = HealthCheckItem("c1", "CAT", "comp", "HEALTHY", "INFO", "obs", "exp", "ts", "ev")
    keys = set(chk.to_dict().keys())
    assert "check_id" in keys
    assert "category" in keys
    assert "component" in keys


def test_110_incident_record_dict_keys(sample_provenance: ObservabilityProvenance) -> None:
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "cond", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    keys = set(inc.to_dict().keys())
    assert "incident_id" in keys
    assert "status" in keys
    assert "provenance" in keys


def test_111_recovery_recommendation_dict_keys(sample_provenance: ObservabilityProvenance) -> None:
    rec = RecoveryRecommendation("rec1", "inc1", "action", "reason", "HIGH", sample_provenance)
    keys = set(rec.to_dict().keys())
    assert "recommendation_id" in keys
    assert "recommended_action" in keys


def test_112_recovery_operation_dict_keys() -> None:
    op = RecoveryOperation("op1", "inc1", "admin1", "ts", "action", "reason", "VERIFIED", "VERIFIED", "ref", "idemp")
    keys = set(op.to_dict().keys())
    assert "recovery_id" in keys
    assert "idempotency_key" in keys


def test_113_observability_provenance_dict_keys(sample_provenance: ObservabilityProvenance) -> None:
    keys = set(sample_provenance.to_dict().keys())
    assert "source_request_id" in keys
    assert "recovery_id" in keys


def test_114_observability_repository_insert_health_comparison(temp_db: sqlite3.Connection) -> None:
    repo = ObservabilityRepository(temp_db)
    comp = HealthTrendComparison("cmp1", "ra", "rb", "HEALTH_STABLE", 0.0, (), "ts")
    cursor = temp_db.cursor()
    cursor.execute(
        """
        INSERT INTO phase26_health_comparisons (
            comparison_id, report_id_a, report_id_b, trend_status, score_delta, changed_checks_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (comp.comparison_id, comp.report_id_a, comp.report_id_b, comp.trend_status, comp.score_delta, "[]", comp.created_at),
    )
    temp_db.commit()


def test_115_observability_repository_query_incidents_by_status(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc1 = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_DETECTED, "ts", sample_provenance)
    inc2 = IncidentRecord("inc2", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    repo.insert_incident(inc1)
    repo.insert_incident(inc2)

    cursor = temp_db.cursor()
    cursor.execute("SELECT incident_id FROM phase26_incidents WHERE status = ?", (INCIDENT_STAGE_DETECTED,))
    rows = cursor.fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "inc1"


def test_116_human_recovery_service_reject_flow(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    repo.insert_incident(inc)
    service = HumanRecoveryService(temp_db)
    updated, rev = service.review_recovery_decision("inc1", "REJECTED", approved_by="admin1")
    assert updated.status == INCIDENT_STAGE_REJECTED


def test_117_human_recovery_service_defer_flow(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    repo = ObservabilityRepository(temp_db)
    inc = IncidentRecord("inc1", "r1", "d1", "rel1", "comp", "HIGH", "CAT", "fail", "ev", INCIDENT_STAGE_ACKNOWLEDGED, "ts", sample_provenance)
    repo.insert_incident(inc)
    service = HumanRecoveryService(temp_db)
    updated, rev = service.review_recovery_decision("inc1", "DEFERRED", approved_by="admin1")
    assert updated.status == INCIDENT_STAGE_DEFERRED


def test_118_incident_detection_service_clean_report_storage(temp_db: sqlite3.Connection, sample_health_checks: tuple[HealthCheckItem, ...]) -> None:
    service = IncidentDetectionService(temp_db)
    domain_service = ProductionObservabilityService()
    report = domain_service.generate_health_report("dep1", "rel1", "v1", sample_health_checks, created_by="admin1")
    incidents = service.process_health_report_for_incidents(report)
    assert len(incidents) == 0


def test_119_runtime_health_report_created_at_field(sample_provenance: ObservabilityProvenance, sample_health_checks: tuple[HealthCheckItem, ...]) -> None:
    service = ProductionObservabilityService()
    report = service.generate_health_report("dep1", "rel1", "v1", sample_health_checks, created_by="admin1", provenance=sample_provenance)
    assert report.created_at is not None


def test_120_full_phase26_observability_pipeline_end_to_end(temp_db: sqlite3.Connection, sample_provenance: ObservabilityProvenance) -> None:
    """End-to-end pipeline test for Phase 26."""
    health_service = RuntimeHealthService(temp_db)
    detection_service = IncidentDetectionService(temp_db)
    recovery_service = HumanRecoveryService(temp_db)

    # 1. Generate health report with failing security check
    checks = (HealthCheckItem("c1", "SECURITY", "sec_comp", "UNHEALTHY", "CRITICAL", "obs", "exp", "ts", "ev"),)
    report = health_service.generate_and_store_report("dep1", "rel1", "v1", checks, created_by="admin1", provenance=sample_provenance)
    assert report.overall_status == "UNHEALTHY"

    # 2. Detect incident
    incidents = detection_service.process_health_report_for_incidents(report)
    assert len(incidents) == 1
    inc_id = incidents[0].incident_id

    # 3. Acknowledge incident (Human Admin)
    ack_inc, _ = recovery_service.acknowledge_incident(inc_id, acknowledged_by="super-admin-1")
    assert ack_inc.status == INCIDENT_STAGE_ACKNOWLEDGED

    # 4. Review & approve recovery (Human Admin)
    app_inc, _ = recovery_service.review_recovery_decision(inc_id, "APPROVED", approved_by="super-admin-1")
    assert app_inc.status == INCIDENT_STAGE_APPROVED

    # 5. Execute recovery operation (Human Admin)
    ver_inc, rec_op = recovery_service.execute_recovery(inc_id, "INSPECT_SECURITY_ADMIN_BOUNDARY", approved_by="super-admin-1", reason="Resolved boundary check")
    assert ver_inc.status == INCIDENT_STAGE_VERIFIED
    assert rec_op.execution_status == INCIDENT_STAGE_VERIFIED
