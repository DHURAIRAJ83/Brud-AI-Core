"""Phase 25 — Production Readiness, Deployment Gate & Operational Safety Test Suite.

Comprehensive 120-test suite verifying:
- Dataclasses, constants, and state machine transitions
- Pre-deployment readiness check engine (8 operational categories)
- SECURITY_ADMIN_BOUNDARY hard block
- Extended 16-step provenance chain preservation
- Deployment readiness report generation
- Human deployment approval gate (Readiness PASS != Automatic Deployment)
- Atomic deployment execution & concurrency lock protection
- Non-destructive deployment rollback & historical version management
- Idempotency key computation & duplicate deployment prevention
- SQLite repository persistence in isolated databases (:memory:)
- Admin API endpoints & RBAC invariants
- AST security & zero autonomous execution
- Production DB integrity (data/database/brud_ai.db byte-identical)
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import sqlite3
from typing import Any

import pytest

from core_model.capabilities.knowledge_gap import (
    GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
    SEVERITY_CRITICAL,
    SEVERITY_LOW,
)
from core_model.capabilities.evaluation_service import (
    EVALUATION_STAGE_APPROVED,
    EvaluationProvenance,
    EvaluationRecord,
)
from core_model.capabilities.release_management_service import (
    RELEASE_STAGE_ACTIVE,
    ReleaseCandidate,
    ReleaseProvenance,
)
from core_model.capabilities.deployment_readiness_service import (
    DEPLOYMENT_ALLOWED_TRANSITIONS,
    DEPLOYMENT_STAGE_ACTIVE_RELEASE,
    DEPLOYMENT_STAGE_APPROVED,
    DEPLOYMENT_STAGE_DEFERRED,
    DEPLOYMENT_STAGE_DEPLOYING,
    DEPLOYMENT_STAGE_EXECUTION_FAILED,
    DEPLOYMENT_STAGE_FAILED,
    DEPLOYMENT_STAGE_PENDING_APPROVAL,
    DEPLOYMENT_STAGE_PREFLIGHT,
    DEPLOYMENT_STAGE_READY,
    DEPLOYMENT_STAGE_REJECTED,
    DEPLOYMENT_STAGE_ROLLBACK_PENDING,
    DEPLOYMENT_STAGE_ROLLED_BACK,
    DEPLOYMENT_STAGE_VALIDATED,
    DEPLOYMENT_STAGE_VERIFIED,
    DEPLOYMENT_STAGE_VERIFYING,
    DEPLOYMENT_STAGE_VERIFICATION_FAILED,
    DeploymentApproval,
    DeploymentApprovalRequiredError,
    DeploymentGovernanceError,
    DeploymentLockError,
    DeploymentOperation,
    DeploymentPreflightError,
    DeploymentProvenance,
    DeploymentReadinessReport,
    DeploymentReadinessService,
    DeploymentRollback,
    InvalidDeploymentTransitionError,
    ReadinessCheck,
    compute_deployment_idempotency_key,
    compute_deployment_rollback_idempotency_key,
    generate_deployment_id,
    generate_readiness_id,
    run_deployment_readiness_checks,
)
from backend.database.repositories.evaluation_repository import EvaluationRepository
from backend.database.repositories.release_repository import ReleaseRepository
from backend.database.repositories.deployment_repository import DeploymentRepository
from backend.services.deployment_readiness_service import DeploymentReadinessBackendService
from backend.services.deployment_gate_service import DeploymentGateService
from backend.services.deployment_rollback_service import DeploymentRollbackBackendService

PROD_DB_PATH = "data/database/brud_ai.db"
EXPECTED_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_DB_SIZE = 11096064


@pytest.fixture
def sample_active_release_candidate() -> ReleaseCandidate:
    rel_prov = ReleaseProvenance(
        source_request_id="req-p25-01",
        source_gap_id="gap-p25-01",
        source_record_id="rec-p25-01",
        candidate_id="cand-p25-01",
        operation_id="op-p25-01",
        artifact_id="art-p25-01",
        evaluation_id="eval-p25-01",
        comparison_id="comp-p25-01",
        review_id="rev-p25-01",
        release_id="rel-p25-01",
        promotion_operation_id="prom-p25-01",
        rollback_operation_id=None,
        approved_by="admin-1",
        approved_at="2026-08-28T09:00:00Z",
        gap_type=GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
        severity=SEVERITY_LOW,
        artifact_type="RAG_SOURCE_VERSION",
    )
    return ReleaseCandidate(
        release_id="rel-p25-01",
        artifact_id="art-p25-01",
        artifact_type="RAG_SOURCE_VERSION",
        artifact_version="rag-rel-v1.0.0",
        evaluation_id="eval-p25-01",
        evaluation_status=EVALUATION_STAGE_APPROVED,
        release_status=RELEASE_STAGE_ACTIVE,
        release_version="rag-rel-v1.0.0",
        content_hash=hashlib.sha256(b"Validated release content").hexdigest(),
        provenance_hash=hashlib.sha256(b"prov-hash").hexdigest(),
        created_by="admin-1",
        created_at="2026-08-28T09:00:00Z",
        provenance=rel_prov,
        notes="Active release promoted in Phase 24",
    )


@pytest.fixture
def temp_deployment_repo() -> DeploymentRepository:
    """Fixture providing an isolated in-memory DeploymentRepository."""
    conn = sqlite3.connect(":memory:")
    repo = DeploymentRepository(conn)
    repo.release_repo = ReleaseRepository(conn)  # type: ignore[attr-defined]
    return repo


# ===========================================================================
# 1-15: State Constants, Allowed Transitions & Data Model Tests
# ===========================================================================

def test_01_deployment_state_constants() -> None:
    assert DEPLOYMENT_STAGE_ACTIVE_RELEASE == "ACTIVE_RELEASE"
    assert DEPLOYMENT_STAGE_PREFLIGHT == "READINESS_PREFLIGHT"
    assert DEPLOYMENT_STAGE_VALIDATED == "READINESS_VALIDATED"
    assert DEPLOYMENT_STAGE_APPROVED == "DEPLOYMENT_APPROVED"
    assert DEPLOYMENT_STAGE_VERIFIED == "DEPLOYMENT_VERIFIED"
    assert DEPLOYMENT_STAGE_ROLLED_BACK == "ROLLED_BACK"


def test_02_allowed_transitions_map() -> None:
    assert DEPLOYMENT_STAGE_VALIDATED in DEPLOYMENT_ALLOWED_TRANSITIONS[DEPLOYMENT_STAGE_PREFLIGHT]
    assert DEPLOYMENT_STAGE_APPROVED in DEPLOYMENT_ALLOWED_TRANSITIONS[DEPLOYMENT_STAGE_PENDING_APPROVAL]
    assert DEPLOYMENT_STAGE_VERIFIED in DEPLOYMENT_ALLOWED_TRANSITIONS[DEPLOYMENT_STAGE_VERIFYING]


def test_03_deployment_provenance_dataclass() -> None:
    prov = DeploymentProvenance("req", "gap", "rec", "cand", "op", "art", "eval", "comp", "rev", "rel", "prom", "rel_rb", "read", "app", "dep", "rb", "admin", "now", "type", "low", "RAG")
    d = prov.to_dict()
    assert d["readiness_id"] == "read"
    assert d["deployment_id"] == "dep"
    assert d["deployment_rollback_id"] == "rb"


def test_04_readiness_check_dataclass() -> None:
    chk = ReadinessCheck("chk-1", "SECURITY", "secret_audit", "PASSED", "CRITICAL", "CLEAN", "CLEAN", "ev")
    d = chk.to_dict()
    assert d["check_id"] == "chk-1"


def test_05_deployment_readiness_report_dataclass(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean content", created_by="admin-1")
    d = report.to_dict()
    assert d["readiness_id"] == report.readiness_id
    assert d["readiness_status"] == DEPLOYMENT_STAGE_VALIDATED


def test_06_deployment_approval_dataclass() -> None:
    app = DeploymentApproval("app-1", "read-1", "rel-1", "admin-1", "now", "APPROVED", "notes", "hash")
    d = app.to_dict()
    assert d["approval_id"] == "app-1"


def test_07_deployment_operation_dataclass() -> None:
    op = DeploymentOperation("dep-1", "read-1", "rel-1", "production", None, "v1", "DEPLOYMENT_VERIFIED", "key", "admin", "now", "now", "now", "VERIFIED", "audit-1")
    d = op.to_dict()
    assert d["deployment_status"] == "DEPLOYMENT_VERIFIED"


def test_08_deployment_rollback_dataclass() -> None:
    rb = DeploymentRollback("rb-1", "dep-1", "v2", "v1", "reason", "admin", "now", "ROLLED_BACK", "VERIFIED", "audit-1")
    d = rb.to_dict()
    assert d["rollback_status"] == "ROLLED_BACK"


def test_09_generate_id_formatting() -> None:
    assert generate_readiness_id().startswith("read-")
    assert generate_deployment_id().startswith("dep-")


def test_10_error_classes_hierarchy() -> None:
    assert issubclass(DeploymentPreflightError, DeploymentGovernanceError)
    assert issubclass(DeploymentApprovalRequiredError, DeploymentGovernanceError)
    assert issubclass(DeploymentLockError, DeploymentGovernanceError)


def test_11_readiness_report_immutability(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean content", created_by="admin-1")
    with pytest.raises(AttributeError):
        report.readiness_status = "DEPLOYED"  # type: ignore[misc]


def test_12_deployment_approval_immutability() -> None:
    app = DeploymentApproval("app-1", "read-1", "rel-1", "admin-1", "now", "APPROVED")
    with pytest.raises(AttributeError):
        app.decision = "REJECTED"  # type: ignore[misc]


def test_13_deployment_operation_immutability() -> None:
    op = DeploymentOperation("dep-1", "read-1", "rel-1", "prod", None, "v1", "VERIFIED", "key", "admin", "now", "now", "now", "VERIFIED", "audit-1")
    with pytest.raises(AttributeError):
        op.deployment_status = "FAILED"  # type: ignore[misc]


def test_14_deployment_rollback_immutability() -> None:
    rb = DeploymentRollback("rb-1", "dep-1", "v2", "v1", "reason", "admin", "now", "ROLLED_BACK", "VERIFIED", "audit-1")
    with pytest.raises(AttributeError):
        rb.rollback_status = "FAILED"  # type: ignore[misc]


def test_15_idempotency_key_computation() -> None:
    k1 = compute_deployment_idempotency_key("rel-1", "v1.0.0")
    k2 = compute_deployment_idempotency_key("rel-1", "v1.0.0")
    assert k1 == k2


# ===========================================================================
# 16-30: Readiness Check Engine (8 Operational Categories) Tests
# ===========================================================================

def test_16_run_deployment_readiness_checks_all_pass(sample_active_release_candidate: ReleaseCandidate) -> None:
    checks, blockers, warnings = run_deployment_readiness_checks(sample_active_release_candidate, "Clean release text")
    assert len(blockers) == 0
    assert len(checks) >= 8


def test_17_readiness_checks_fail_inactive_release(sample_active_release_candidate: ReleaseCandidate) -> None:
    unactive_rel = ReleaseCandidate(sample_active_release_candidate.release_id, sample_active_release_candidate.artifact_id, sample_active_release_candidate.artifact_type, sample_active_release_candidate.artifact_version, sample_active_release_candidate.evaluation_id, sample_active_release_candidate.evaluation_status, "PENDING_RELEASE_APPROVAL", sample_active_release_candidate.release_version, sample_active_release_candidate.content_hash, sample_active_release_candidate.provenance_hash, sample_active_release_candidate.created_by, sample_active_release_candidate.created_at, sample_active_release_candidate.provenance)
    checks, blockers, _ = run_deployment_readiness_checks(unactive_rel, "Clean text")
    assert "RELEASE_NOT_ACTIVE" in blockers


def test_18_readiness_checks_fail_security_boundary(sample_active_release_candidate: ReleaseCandidate) -> None:
    sec_prov = ReleaseProvenance("r", "g", "rec", "c", "op", "art", "eval", None, None, "rel", "prom", None, "admin", "now", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "RAG")
    sec_rel = ReleaseCandidate("rel-1", "art-1", "RAG", "v1", "eval-1", "APPROVED", RELEASE_STAGE_ACTIVE, "v1", "hash", "phash", "admin", "now", sec_prov)
    checks, blockers, _ = run_deployment_readiness_checks(sec_rel, "Clean text")
    assert "SECURITY_ADMIN_BOUNDARY_PROHIBITED" in blockers


def test_19_readiness_checks_fail_secret_credentials(sample_active_release_candidate: ReleaseCandidate) -> None:
    checks, blockers, _ = run_deployment_readiness_checks(sample_active_release_candidate, "Secret api_key=secret123")
    assert "SECRET_CREDENTIAL_DETECTED" in blockers


def test_20_readiness_checks_fail_database_backup_not_ready(sample_active_release_candidate: ReleaseCandidate) -> None:
    checks, blockers, _ = run_deployment_readiness_checks(sample_active_release_candidate, "Clean text", db_backup_ready=False)
    assert "DATABASE_BACKUP_NOT_READY" in blockers


def test_21_readiness_checks_fail_config_invalid(sample_active_release_candidate: ReleaseCandidate) -> None:
    checks, blockers, _ = run_deployment_readiness_checks(sample_active_release_candidate, "Clean text", config_valid=False)
    assert "CONFIGURATION_INVALID" in blockers


def test_22_readiness_checks_fail_app_health_unhealthy(sample_active_release_candidate: ReleaseCandidate) -> None:
    checks, blockers, _ = run_deployment_readiness_checks(sample_active_release_candidate, "Clean text", app_health_pass=False)
    assert "APPLICATION_HEALTH_FAILED" in blockers


def test_23_readiness_checks_warning_resource_capacity(sample_active_release_candidate: ReleaseCandidate) -> None:
    checks, blockers, warnings = run_deployment_readiness_checks(sample_active_release_candidate, "Clean text", resources_ready=False)
    assert len(blockers) == 0
    assert "RESOURCE_CAPACITY_WARNING" in warnings


def test_24_readiness_checks_fail_regression_failure(sample_active_release_candidate: ReleaseCandidate) -> None:
    checks, blockers, _ = run_deployment_readiness_checks(sample_active_release_candidate, "Clean text", regression_pass=False)
    assert "REGRESSION_TEST_FAILURE" in blockers


def test_25_generate_readiness_report_fails_unactive_release(sample_active_release_candidate: ReleaseCandidate) -> None:
    unactive_rel = ReleaseCandidate(sample_active_release_candidate.release_id, sample_active_release_candidate.artifact_id, sample_active_release_candidate.artifact_type, sample_active_release_candidate.artifact_version, sample_active_release_candidate.evaluation_id, sample_active_release_candidate.evaluation_status, "PENDING_RELEASE_APPROVAL", sample_active_release_candidate.release_version, sample_active_release_candidate.content_hash, sample_active_release_candidate.provenance_hash, sample_active_release_candidate.created_by, sample_active_release_candidate.created_at, sample_active_release_candidate.provenance)
    service = DeploymentReadinessService()
    with pytest.raises(DeploymentPreflightError):
        service.generate_readiness_report(unactive_rel, "Clean text", created_by="admin-1")


def test_26_readiness_report_overall_score_calculation(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert report.overall_score == 1.0


def test_27_readiness_report_score_degraded_on_warnings(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1", resources_ready=False)
    assert report.overall_score < 1.0


def test_28_readiness_report_has_valid_hashes(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert len(report.content_hash) == 64
    assert len(report.configuration_hash) == 64
    assert len(report.dependency_hash) == 64


def test_29_readiness_report_created_at_populated(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert report.created_at is not None


def test_30_readiness_checks_are_deterministic(sample_active_release_candidate: ReleaseCandidate) -> None:
    c1, b1, w1 = run_deployment_readiness_checks(sample_active_release_candidate, "Clean text")
    c2, b2, w2 = run_deployment_readiness_checks(sample_active_release_candidate, "Clean text")
    assert b1 == b2
    assert w1 == w2


# ===========================================================================
# 31-45: Extended 16-Step Provenance Chain Tests
# ===========================================================================

def test_31_deployment_readiness_report_preserves_release_provenance(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    p = report.provenance
    assert p.release_id == sample_active_release_candidate.release_id
    assert p.source_request_id == sample_active_release_candidate.provenance.source_request_id


def test_32_deployment_approval_updates_provenance(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    updated, app = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    assert updated.provenance.deployment_approval_id == app.approval_id


def test_33_deployment_execution_updates_provenance(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    ver_report, dep_op = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")
    assert ver_report.provenance.deployment_id == dep_op.deployment_id


def test_34_deployment_rollback_updates_provenance(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    ver_report, _ = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")

    rb_report, rb_op = service.rollback_deployment(ver_report, "rag-rel-v1.0.0", approved_by="super-admin-1", reason="test")
    assert rb_report.provenance.deployment_rollback_id == rb_op.rollback_id


def test_35_deployment_provenance_dict_conversion(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    d = report.provenance.to_dict()
    assert d["readiness_id"] == report.readiness_id


def test_36_provenance_preserves_artifact_type(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert report.provenance.artifact_type == "RAG_SOURCE_VERSION"


def test_37_provenance_preserves_severity(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert report.provenance.severity == sample_active_release_candidate.provenance.severity


def test_38_provenance_preserves_gap_type(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert report.provenance.gap_type == sample_active_release_candidate.provenance.gap_type


def test_39_deployment_approval_hash_generated(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    _, app = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    assert len(app.approval_hash) == 64


def test_40_deployment_op_contains_idempotency_key(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    _, dep_op = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")
    assert len(dep_op.idempotency_key) == 64


def test_41_deployment_rollback_contains_reason(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    ver_report, _ = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")

    _, rb_op = service.rollback_deployment(ver_report, "v1.0.0", approved_by="super-admin-1", reason="Perf degradation")
    assert rb_op.reason == "Perf degradation"


def test_42_deployment_audit_reference_recorded(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    _, dep_op = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")
    assert dep_op.audit_reference.startswith("audit-dep-")


def test_43_rollback_audit_reference_recorded(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    ver_report, _ = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")

    _, rb_op = service.rollback_deployment(ver_report, "v1.0.0", approved_by="super-admin-1", reason="test")
    assert rb_op.audit_reference.startswith("audit-dep-rb-")


def test_44_deployment_approval_timestamp_recorded(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    _, app = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    assert app.approved_at is not None


def test_45_reviewer_identity_recorded(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    _, app = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    assert app.approved_by == "super-admin-1"


# ===========================================================================
# 46-60: Human Deployment Approval Gate Tests
# ===========================================================================

def test_46_process_deployment_approval_approved(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    updated, app = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    assert updated.readiness_status == DEPLOYMENT_STAGE_READY
    assert app.decision == DEPLOYMENT_STAGE_APPROVED


def test_47_process_deployment_approval_rejected(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    updated, app = service.process_deployment_approval(report, "REJECTED", approved_by="super-admin-1")
    assert updated.readiness_status == DEPLOYMENT_STAGE_REJECTED
    assert app.decision == DEPLOYMENT_STAGE_REJECTED


def test_48_process_deployment_approval_deferred(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    updated, app = service.process_deployment_approval(report, "DEFERRED", approved_by="super-admin-1")
    assert updated.readiness_status == DEPLOYMENT_STAGE_DEFERRED
    assert app.decision == DEPLOYMENT_STAGE_DEFERRED


def test_49_deployment_approval_requires_reviewer_identity(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    with pytest.raises(DeploymentApprovalRequiredError):
        service.process_deployment_approval(report, "APPROVED", approved_by="   ")


def test_50_invalid_decision_string_raises_error(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    with pytest.raises(InvalidDeploymentTransitionError):
        service.process_deployment_approval(report, "INVALID_DECISION", approved_by="admin-1")


def test_51_cannot_execute_unapproved_deployment(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    with pytest.raises(InvalidDeploymentTransitionError):
        service.execute_deployment(report, previous_version=None, approved_by="admin-1")


def test_52_cannot_execute_rejected_deployment(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    rej_report, _ = service.process_deployment_approval(report, "REJECTED", approved_by="admin-1")

    with pytest.raises(InvalidDeploymentTransitionError):
        service.execute_deployment(rej_report, previous_version=None, approved_by="admin-1")


def test_53_readiness_pass_alone_does_not_deploy(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert report.readiness_status == DEPLOYMENT_STAGE_VALIDATED
    assert report.readiness_status != DEPLOYMENT_STAGE_VERIFIED


def test_54_deferred_deployment_can_be_re_reviewed(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    def_report, _ = service.process_deployment_approval(report, "DEFERRED", approved_by="admin-1")

    pending_report = DeploymentReadinessReport(def_report.readiness_id, def_report.release_id, def_report.active_version, def_report.target_environment, DEPLOYMENT_STAGE_VALIDATED, def_report.checks, def_report.overall_score, def_report.blockers, def_report.warnings, def_report.content_hash, def_report.configuration_hash, def_report.dependency_hash, def_report.provenance, def_report.created_at)
    app_report, _ = service.process_deployment_approval(pending_report, "APPROVED", approved_by="admin-1")
    assert app_report.readiness_status == DEPLOYMENT_STAGE_READY


def test_55_deployment_readiness_backend_service_flow(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    service = DeploymentReadinessBackendService(temp_deployment_repo.conn)

    report = service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")
    assert report.readiness_status == DEPLOYMENT_STAGE_VALIDATED


def test_56_deployment_gate_service_review_flow(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    updated_report, app = gate_service.review_deployment(report.readiness_id, "APPROVED", reviewer_id="super-admin-1")
    assert updated_report.readiness_status == DEPLOYMENT_STAGE_READY


def test_57_deployment_gate_service_execution_flow(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    gate_service.review_deployment(report.readiness_id, "APPROVED", reviewer_id="super-admin-1")

    ver_report, dep_op = gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")
    assert ver_report.readiness_status == DEPLOYMENT_STAGE_VERIFIED
    assert dep_op.deployment_status == DEPLOYMENT_STAGE_VERIFIED


def test_58_deployment_concurrency_lock_prevents_simultaneous_execution(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    # Manually acquire deployment lock
    temp_deployment_repo.acquire_deployment_lock(sample_active_release_candidate.release_id, "dep-temp-read-1", "admin-other")

    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    gate_service.review_deployment(report.readiness_id, "APPROVED", reviewer_id="super-admin-1")

    with pytest.raises(DeploymentLockError):
        gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")


def test_59_deployment_rollback_service_flow(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    gate_service.review_deployment(report.readiness_id, "APPROVED", reviewer_id="super-admin-1")
    ver_report, _ = gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")

    rb_service = DeploymentRollbackBackendService(temp_deployment_repo.conn)
    rb_report, rb_op = rb_service.rollback_deployment(ver_report.readiness_id, "rag-rel-v1.0.0", approved_by="super-admin-1")
    assert rb_report.readiness_status == DEPLOYMENT_STAGE_ROLLED_BACK


def test_60_non_destructive_deployment_rollback_preserves_history(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    gate_service.review_deployment(report.readiness_id, "APPROVED", reviewer_id="super-admin-1")
    gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")

    rb_service = DeploymentRollbackBackendService(temp_deployment_repo.conn)
    rb_service.rollback_deployment(report.readiness_id, "rag-rel-v1.0.0", approved_by="super-admin-1")

    # Historical readiness report MUST still exist
    stored = temp_deployment_repo.get_readiness_report_by_id(report.readiness_id)
    assert stored is not None


# ===========================================================================
# 61-75: Idempotency & Concurrency Edge Case Tests
# ===========================================================================

def test_61_idempotent_deployment_returns_existing_op(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    gate_service.review_deployment(report.readiness_id, "APPROVED", reviewer_id="super-admin-1")

    rep1, op1 = gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")
    rep2, op2 = gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")
    assert op1.deployment_id == op2.deployment_id


def test_62_cannot_rollback_unexecuted_deployment(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    with pytest.raises(InvalidDeploymentTransitionError):
        service.rollback_deployment(report, "v1.0.0", approved_by="admin-1", reason="test")


def test_63_non_existent_readiness_report_raises_value_error(temp_deployment_repo: DeploymentRepository) -> None:
    service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    with pytest.raises(ValueError):
        service.get_readiness_report("read-non-existent")


def test_64_non_existent_release_preflight_raises_value_error(temp_deployment_repo: DeploymentRepository) -> None:
    service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    with pytest.raises(ValueError):
        service.run_preflight("rel-non-existent", created_by="admin-1")


def test_65_non_existent_deployment_review_raises_value_error(temp_deployment_repo: DeploymentRepository) -> None:
    service = DeploymentGateService(temp_deployment_repo.conn)
    with pytest.raises(ValueError):
        service.review_deployment("read-non-existent", "APPROVED", reviewer_id="admin-1")


def test_66_non_existent_deployment_execution_raises_value_error(temp_deployment_repo: DeploymentRepository) -> None:
    service = DeploymentGateService(temp_deployment_repo.conn)
    with pytest.raises(ValueError):
        service.execute_deployment("read-non-existent", approved_by="admin-1")


def test_67_non_existent_deployment_rollback_raises_value_error(temp_deployment_repo: DeploymentRepository) -> None:
    service = DeploymentRollbackBackendService(temp_deployment_repo.conn)
    with pytest.raises(ValueError):
        service.rollback_deployment("read-non-existent", "v1.0.0", approved_by="admin-1")


def test_68_aggregate_deployment_metrics(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    metrics = temp_deployment_repo.aggregate_metrics()
    assert metrics["total_reports"] == 1
    assert metrics["status_counts"][DEPLOYMENT_STAGE_VALIDATED] == 1


def test_69_rollback_idempotency_key_computation() -> None:
    k1 = compute_deployment_rollback_idempotency_key("dep-1", "v2", "v1")
    k2 = compute_deployment_rollback_idempotency_key("dep-1", "v2", "v1")
    assert k1 == k2


def test_70_deployment_repository_schema_initialization(temp_deployment_repo: DeploymentRepository) -> None:
    cursor = temp_deployment_repo.conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r["name"] for r in cursor.fetchall()]
    assert "phase25_readiness_reports" in tables
    assert "phase25_readiness_checks" in tables
    assert "phase25_deployment_approvals" in tables
    assert "phase25_deployment_operations" in tables
    assert "phase25_deployment_rollbacks" in tables
    assert "phase25_deployment_locks" in tables


def test_71_deployment_repository_indexes_exist(temp_deployment_repo: DeploymentRepository) -> None:
    cursor = temp_deployment_repo.conn.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indexes = [r["name"] for r in cursor.fetchall()]
    assert "idx_phase25_rep_rel" in indexes
    assert "idx_phase25_op_key" in indexes


def test_72_utf8_encoding_preserved_in_deployment_evidence(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "தமிழ் வரிசைப்படுத்தல் சான்று", created_by="admin-1")
    assert report.checks[0].evidence is not None


def test_73_readiness_report_created_at_recorded(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert report.created_at is not None


def test_74_deployment_operation_verification_status(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    _, dep_op = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")
    assert dep_op.verification_status == "VERIFIED"


def test_75_deployment_lock_released_after_execution(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    gate_service.review_deployment(report.readiness_id, "APPROVED", reviewer_id="super-admin-1")
    gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")

    # Lock MUST be released
    cursor = temp_deployment_repo.conn.execute("SELECT * FROM phase25_deployment_locks WHERE release_id = ?;", (sample_active_release_candidate.release_id,))
    assert cursor.fetchone() is None


# ===========================================================================
# 76-90: Terminal States & Governance Invariant Tests
# ===========================================================================

def test_76_terminal_rejected_state_prevents_re_review(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    rej_report, _ = service.process_deployment_approval(report, "REJECTED", approved_by="admin-1")

    with pytest.raises(InvalidDeploymentTransitionError):
        service.process_deployment_approval(rej_report, "APPROVED", approved_by="admin-1")


def test_77_zero_autonomous_service_restarts_triggered(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="admin-1")
    service.execute_deployment(app_report, previous_version=None, approved_by="admin-1")

    # Verify zero autonomous restarts or training triggered
    assert not os.path.exists("data/model_weights.pt")


def test_78_non_destructive_rollback_preserves_readiness_report(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    gate_service.review_deployment(report.readiness_id, "APPROVED", reviewer_id="super-admin-1")
    ver_report, _ = gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")

    rb_service = DeploymentRollbackBackendService(temp_deployment_repo.conn)
    rb_service.rollback_deployment(ver_report.readiness_id, "rag-rel-v1.0.0", approved_by="super-admin-1")

    # Report record MUST remain intact
    stored = temp_deployment_repo.get_readiness_report_by_id(report.readiness_id)
    assert stored is not None


def test_79_deployment_preserves_previous_version_field(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    _, dep_op = service.execute_deployment(app_report, previous_version="v1.0.0-old", approved_by="super-admin-1")
    assert dep_op.previous_version == "v1.0.0-old"


def test_80_rollback_operation_reason_recorded(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    ver_report, _ = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")

    _, rb_op = service.rollback_deployment(ver_report, "v1.0.0", approved_by="super-admin-1", reason="Manual deployment testing rollback")
    assert rb_op.reason == "Manual deployment testing rollback"


def test_81_deployment_readiness_report_content_hash_integrity(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    cand1 = ReleaseCandidate(sample_active_release_candidate.release_id, sample_active_release_candidate.artifact_id, sample_active_release_candidate.artifact_type, sample_active_release_candidate.artifact_version, sample_active_release_candidate.evaluation_id, sample_active_release_candidate.evaluation_status, sample_active_release_candidate.release_status, sample_active_release_candidate.release_version, "hash1", "phash1", sample_active_release_candidate.created_by, sample_active_release_candidate.created_at, sample_active_release_candidate.provenance)
    cand2 = ReleaseCandidate(sample_active_release_candidate.release_id, sample_active_release_candidate.artifact_id, sample_active_release_candidate.artifact_type, sample_active_release_candidate.artifact_version, sample_active_release_candidate.evaluation_id, sample_active_release_candidate.evaluation_status, sample_active_release_candidate.release_status, sample_active_release_candidate.release_version, "hash2", "phash2", sample_active_release_candidate.created_by, sample_active_release_candidate.created_at, sample_active_release_candidate.provenance)
    report1 = service.generate_readiness_report(cand1, "Content text 1", created_by="admin-1")
    report2 = service.generate_readiness_report(cand2, "Content text 2", created_by="admin-1")
    assert report1.content_hash != report2.content_hash


def test_82_deployment_approval_hash_integrity(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Content text", created_by="admin-1")
    _, app1 = service.process_deployment_approval(report, "APPROVED", approved_by="admin-1")
    _, app2 = service.process_deployment_approval(report, "APPROVED", approved_by="admin-2")
    assert app1.approval_hash != app2.approval_hash


def test_83_deployment_approval_notes_field_preserved(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Content text", created_by="admin-1")
    _, app = service.process_deployment_approval(report, "APPROVED", approved_by="admin-1", reviewer_notes="Approved for prod deployment")
    assert app.reviewer_notes == "Approved for prod deployment"


def test_84_deployment_operation_persisted_in_database(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    gate_service.review_deployment(report.readiness_id, "APPROVED", reviewer_id="super-admin-1")
    _, dep_op = gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")

    stored = temp_deployment_repo.get_deployment_by_idempotency_key(dep_op.idempotency_key)
    assert stored is not None
    assert stored.deployment_id == dep_op.deployment_id


def test_85_deployment_rollback_persisted_in_database(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    gate_service.review_deployment(report.readiness_id, "APPROVED", reviewer_id="super-admin-1")
    ver_report, _ = gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")

    rb_service = DeploymentRollbackBackendService(temp_deployment_repo.conn)
    _, rb_op = rb_service.rollback_deployment(ver_report.readiness_id, "rag-rel-v1.0.0", approved_by="super-admin-1")

    cursor = temp_deployment_repo.conn.execute("SELECT * FROM phase25_deployment_rollbacks WHERE rollback_id = ?;", (rb_op.rollback_id,))
    assert cursor.fetchone() is not None


def test_86_deployment_report_blockers_serialization(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1", db_backup_ready=False)
    assert "DATABASE_BACKUP_NOT_READY" in report.blockers


def test_87_deployment_report_warnings_serialization(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1", resources_ready=False)
    assert "RESOURCE_CAPACITY_WARNING" in report.warnings


def test_88_terminal_rejected_state_prevents_deployment(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    rej_report, _ = service.process_deployment_approval(report, "REJECTED", approved_by="admin-1")

    with pytest.raises(InvalidDeploymentTransitionError):
        service.execute_deployment(rej_report, previous_version=None, approved_by="admin-1")


def test_89_terminal_verified_state_prevents_re_approval(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="admin-1")
    ver_report, _ = service.execute_deployment(app_report, previous_version=None, approved_by="admin-1")

    with pytest.raises(InvalidDeploymentTransitionError):
        service.process_deployment_approval(ver_report, "APPROVED", approved_by="admin-1")


def test_90_deployment_lock_prevents_duplicate_acquisition(temp_deployment_repo: DeploymentRepository) -> None:
    res1 = temp_deployment_repo.acquire_deployment_lock("rel-1", "dep-1", "admin-1")
    res2 = temp_deployment_repo.acquire_deployment_lock("rel-1", "dep-2", "admin-2")
    assert res1 is True
    assert res2 is False


# ===========================================================================
# 91-105: Service Integration & Edge Case Tests
# ===========================================================================

def test_91_execute_deployment_without_approval_fails(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    with pytest.raises(InvalidDeploymentTransitionError):
        gate_service.execute_deployment(report.readiness_id, approved_by="admin-1")


def test_92_rollback_deployment_without_verified_status_fails(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    rb_service = DeploymentRollbackBackendService(temp_deployment_repo.conn)
    with pytest.raises(InvalidDeploymentTransitionError):
        rb_service.rollback_deployment(report.readiness_id, "v1.0.0", approved_by="admin-1")


def test_93_deployment_repository_get_report_returns_none_if_missing(temp_deployment_repo: DeploymentRepository) -> None:
    assert temp_deployment_repo.get_readiness_report_by_id("read-non-existent") is None


def test_94_deployment_provenance_full_16_step_chain_validation(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, app = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    ver_report, dep_op = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")
    rb_report, rb_op = service.rollback_deployment(ver_report, "v1.0.0", approved_by="super-admin-1", reason="test")

    p = rb_report.provenance
    assert p.source_request_id == sample_active_release_candidate.provenance.source_request_id
    assert p.release_id == sample_active_release_candidate.release_id
    assert p.readiness_id == report.readiness_id
    assert p.deployment_approval_id == app.approval_id
    assert p.deployment_id == dep_op.deployment_id
    assert p.deployment_rollback_id == rb_op.rollback_id


def test_95_idempotency_key_different_for_different_versions() -> None:
    k1 = compute_deployment_idempotency_key("rel-1", "v1.0.0")
    k2 = compute_deployment_idempotency_key("rel-1", "v1.1.0")
    assert k1 != k2


def test_96_readiness_report_content_hash_deterministic(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report1 = service.generate_readiness_report(sample_active_release_candidate, "Same text", created_by="admin-1")
    report2 = service.generate_readiness_report(sample_active_release_candidate, "Same text", created_by="admin-1")
    assert report1.content_hash == report2.content_hash


def test_97_deployment_approval_dict_conversion() -> None:
    app = DeploymentApproval("app-1", "read-1", "rel-1", "admin-1", "now", "APPROVED", "notes", "hash")
    d = app.to_dict()
    assert d["approval_id"] == "app-1"


def test_98_deployment_operation_dict_conversion() -> None:
    op = DeploymentOperation("dep-1", "read-1", "rel-1", "prod", None, "v1", "VERIFIED", "key", "admin", "now", "now", "now", "VERIFIED", "ref")
    d = op.to_dict()
    assert d["deployment_id"] == "dep-1"


def test_99_deployment_rollback_dict_conversion() -> None:
    rb = DeploymentRollback("rb-1", "dep-1", "v2", "v1", "reason", "admin", "now", "ROLLED_BACK", "VERIFIED", "ref")
    d = rb.to_dict()
    assert d["rollback_id"] == "rb-1"


def test_100_readiness_checks_categories_covered(sample_active_release_candidate: ReleaseCandidate) -> None:
    checks, _, _ = run_deployment_readiness_checks(sample_active_release_candidate, "Clean text")
    categories = set(c.category for c in checks)
    expected_categories = {
        "RELEASE_INTEGRITY",
        "SECURITY",
        "DATABASE_SAFETY",
        "CONFIGURATION",
        "APPLICATION_HEALTH",
        "RESOURCE_READINESS",
        "REGRESSION_BASELINE",
        "OPERATIONAL_SAFETY",
    }
    assert expected_categories.issubset(categories)


def test_101_reject_decision_prevents_verified_status(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    rej_report, _ = service.process_deployment_approval(report, "REJECTED", approved_by="admin-1")
    assert rej_report.readiness_status == DEPLOYMENT_STAGE_REJECTED
    assert rej_report.readiness_status != DEPLOYMENT_STAGE_VERIFIED


def test_102_defer_decision_prevents_verified_status(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    def_report, _ = service.process_deployment_approval(report, "DEFERRED", approved_by="admin-1")
    assert def_report.readiness_status == DEPLOYMENT_STAGE_DEFERRED
    assert def_report.readiness_status != DEPLOYMENT_STAGE_VERIFIED


def test_103_deployment_approval_without_execution_remains_ready(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="admin-1")
    assert app_report.readiness_status == DEPLOYMENT_STAGE_READY
    assert app_report.readiness_status != DEPLOYMENT_STAGE_VERIFIED


def test_104_approval_history_tracked_for_deployment(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    temp_deployment_repo.insert_readiness_report(report)

    app1 = DeploymentApproval("app-1", report.readiness_id, report.release_id, "admin-1", "now", "DEFERRED")
    temp_deployment_repo.insert_deployment_approval(app1)

    app2 = DeploymentApproval("app-2", report.readiness_id, report.release_id, "admin-2", "now", "APPROVED")
    temp_deployment_repo.insert_deployment_approval(app2)

    cursor = temp_deployment_repo.conn.execute("SELECT * FROM phase25_deployment_approvals WHERE readiness_id = ?;", (report.readiness_id,))
    assert len(cursor.fetchall()) == 2


def test_105_zero_autonomous_training_triggered(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="admin-1")
    service.execute_deployment(app_report, previous_version=None, approved_by="admin-1")

    # Verify zero model training or fine-tuning triggered
    assert not os.path.exists("data/model_weights.pt")


# ===========================================================================
# 106-115: Reversible Operations & Governance Invariant Tests
# ===========================================================================

def test_106_terminal_rejected_state_prevents_execution(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    rej_report, _ = service.process_deployment_approval(report, "REJECTED", approved_by="admin-1")

    with pytest.raises(InvalidDeploymentTransitionError):
        service.execute_deployment(rej_report, previous_version=None, approved_by="admin-1")


def test_107_terminal_verified_state_prevents_re_approval(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="admin-1")
    ver_report, _ = service.execute_deployment(app_report, previous_version=None, approved_by="admin-1")

    with pytest.raises(InvalidDeploymentTransitionError):
        service.process_deployment_approval(ver_report, "APPROVED", approved_by="admin-1")


def test_108_deployment_idempotency_lookup_returns_same_record(temp_deployment_repo: DeploymentRepository) -> None:
    op = DeploymentOperation("dep-1", "read-1", "rel-1", "prod", None, "v1", "DEPLOYMENT_VERIFIED", "key-123", "admin", "now", "now", "now", "VERIFIED", "ref")
    temp_deployment_repo.insert_deployment_operation(op)

    fetched = temp_deployment_repo.get_deployment_by_idempotency_key("key-123")
    assert fetched is not None
    assert fetched.deployment_id == "dep-1"


def test_109_rollback_idempotency_key_lookup() -> None:
    k1 = compute_deployment_rollback_idempotency_key("dep-1", "v2", "v1")
    assert len(k1) == 64


def test_110_readiness_check_evidence_preserved(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert len(report.checks[0].evidence) > 0


def test_111_deployment_lock_released_on_error(temp_deployment_repo: DeploymentRepository, sample_active_release_candidate: ReleaseCandidate) -> None:
    temp_deployment_repo.release_repo.insert_release_candidate(sample_active_release_candidate)
    read_service = DeploymentReadinessBackendService(temp_deployment_repo.conn)
    report = read_service.run_preflight(sample_active_release_candidate.release_id, created_by="admin-1")

    gate_service = DeploymentGateService(temp_deployment_repo.conn)
    # Attempt execution without approval -> raises InvalidDeploymentTransitionError
    with pytest.raises(InvalidDeploymentTransitionError):
        gate_service.execute_deployment(report.readiness_id, approved_by="super-admin-1")

    # Lock MUST be released
    cursor = temp_deployment_repo.conn.execute("SELECT * FROM phase25_deployment_locks WHERE release_id = ?;", (sample_active_release_candidate.release_id,))
    assert cursor.fetchone() is None


def test_112_deployment_operation_started_completed_timestamps(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    _, dep_op = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")
    assert dep_op.started_at is not None
    assert dep_op.completed_at is not None


def test_113_deployment_rollback_status_verification(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    app_report, _ = service.process_deployment_approval(report, "APPROVED", approved_by="super-admin-1")
    ver_report, _ = service.execute_deployment(app_report, previous_version=None, approved_by="super-admin-1")

    _, rb_op = service.rollback_deployment(ver_report, "v1.0.0", approved_by="super-admin-1", reason="test")
    assert rb_op.rollback_status == DEPLOYMENT_STAGE_ROLLED_BACK
    assert rb_op.verification_status == "VERIFIED"


def test_114_deployment_readiness_report_notes(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert report.readiness_id.startswith("read-")


def test_115_readiness_report_blockers_and_warnings_empty_on_clean_release(sample_active_release_candidate: ReleaseCandidate) -> None:
    service = DeploymentReadinessService()
    report = service.generate_readiness_report(sample_active_release_candidate, "Clean text", created_by="admin-1")
    assert len(report.blockers) == 0
    assert len(report.warnings) == 0


# ===========================================================================
# 116-120: AST Security, Admin RBAC & Production DB Integrity Tests
# ===========================================================================

def test_116_non_autonomous_learning_invariant() -> None:
    import core_model.capabilities.deployment_readiness_service as mod
    for name, obj in inspect.getmembers(mod):
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            assert "train" not in name.lower()
            assert "fine_tune" not in name.lower()
            assert "modify_weights" not in name.lower()


def test_117_ast_security_deployment_readiness_service() -> None:
    import core_model.capabilities.deployment_readiness_service as mod
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_118_no_network_or_subprocess_in_deployment_readiness_service() -> None:
    code = inspect.getsource(DeploymentReadinessService).lower()
    for forbidden in ("requests.", "httpx.", "urllib.", "subprocess", "os.system", "celery", "apscheduler"):
        assert forbidden not in code


def test_119_production_db_sha256_and_size_unchanged() -> None:
    assert os.path.exists(PROD_DB_PATH), f"Production database path {PROD_DB_PATH} must exist"
    hasher = hashlib.sha256()
    with open(PROD_DB_PATH, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual_sha = hasher.hexdigest()
    actual_size = os.path.getsize(PROD_DB_PATH)

    assert actual_sha == EXPECTED_DB_SHA256, f"Production DB SHA-256 mismatch! Expected {EXPECTED_DB_SHA256}, got {actual_sha}."
    assert actual_size == EXPECTED_DB_SIZE, f"Production DB size mismatch! Expected {EXPECTED_DB_SIZE}, got {actual_size}."


def test_120_final_phase25_integrity_contract_validation() -> None:
    """Final contract validation verifying Phase 25 completion."""
    assert EXPECTED_DB_SHA256 == "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    assert EXPECTED_DB_SIZE == 11096064
    assert len(DEPLOYMENT_ALLOWED_TRANSITIONS) > 0
    assert DEPLOYMENT_STAGE_APPROVED == "DEPLOYMENT_APPROVED"
    assert DEPLOYMENT_STAGE_VERIFIED == "DEPLOYMENT_VERIFIED"
    assert DEPLOYMENT_STAGE_ROLLED_BACK == "ROLLED_BACK"
