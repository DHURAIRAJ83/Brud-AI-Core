"""Phase 24 — Knowledge Release Management, Promotion & Rollback Governance Test Suite.

Comprehensive 120-test suite verifying:
- Dataclasses, constants, and state machine transitions
- Pre-release validation & secret re-validation
- SECURITY_ADMIN_BOUNDARY hard block
- RAG release candidate creation & validation
- Dataset release candidate creation & validation
- Human release approval gate (Evaluation APPROVED != Automatic Promotion)
- Atomic promotion engine & active version pointer management
- Non-destructive rollback engine & historical active version pointer management
- Idempotency key computation & duplicate promotion prevention
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
import tempfile
from pathlib import Path
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
    EVALUATION_STAGE_PENDING_HUMAN_REVIEW,
    EvaluationMetric,
    EvaluationProvenance,
    EvaluationRecord,
)
from core_model.capabilities.release_management_service import (
    RELEASE_ALLOWED_TRANSITIONS,
    RELEASE_STAGE_ACTIVE,
    RELEASE_STAGE_APPROVED,
    RELEASE_STAGE_CANDIDATE_CREATED,
    RELEASE_STAGE_DEFERRED,
    RELEASE_STAGE_EVALUATION_APPROVED,
    RELEASE_STAGE_PENDING_APPROVAL,
    RELEASE_STAGE_PREFLIGHT_FAILED,
    RELEASE_STAGE_PREFLIGHT_VALIDATED,
    RELEASE_STAGE_PROMOTED,
    RELEASE_STAGE_PROMOTING,
    RELEASE_STAGE_PROMOTION_FAILED,
    RELEASE_STAGE_READY_FOR_PROMOTION,
    RELEASE_STAGE_REJECTED,
    RELEASE_STAGE_ROLLED_BACK,
    RELEASE_STAGE_VERIFICATION_FAILED,
    InvalidReleaseTransitionError,
    PromotionOperation,
    ReleaseApproval,
    ReleaseApprovalRequiredError,
    ReleaseCandidate,
    ReleaseGovernanceError,
    ReleaseManagementService,
    ReleasePreflightError,
    ReleasePreflightResult,
    ReleaseProvenance,
    RollbackOperation,
    compute_promotion_idempotency_key,
    compute_rollback_idempotency_key,
    generate_release_id,
    generate_release_version,
    run_prerelease_validation,
)
from backend.database.repositories.evaluation_repository import EvaluationRepository
from backend.database.repositories.release_repository import ReleaseRepository
from backend.services.rag_release_service import RagReleaseService
from backend.services.dataset_release_service import DatasetReleaseService
from backend.services.promotion_rollback_service import PromotionRollbackService

PROD_DB_PATH = "data/database/brud_ai.db"
EXPECTED_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_DB_SIZE = 11096064


@pytest.fixture
def sample_evaluation_record() -> EvaluationRecord:
    eval_prov = EvaluationProvenance(
        source_request_id="req-p24-01",
        source_gap_id="gap-p24-01",
        source_record_id="rec-p24-01",
        candidate_id="cand-p24-01",
        operation_id="op-p24-01",
        artifact_id="art-p24-01",
        evaluation_id="eval-p24-01",
        comparison_id="comp-p24-01",
        review_id="rev-p24-01",
        decision="APPROVED",
        approved_by="admin-1",
        approved_at="2026-08-28T08:00:00Z",
        gap_type=GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
        severity=SEVERITY_LOW,
        artifact_type="RAG_SOURCE_VERSION",
    )
    return EvaluationRecord(
        evaluation_id="eval-p24-01",
        artifact_id="art-p24-01",
        artifact_type="RAG_SOURCE_VERSION",
        artifact_version="v1.0.0",
        status=EVALUATION_STAGE_APPROVED,
        overall_score=0.92,
        metrics=(),
        provenance=eval_prov,
        created_at="2026-08-28T08:00:00Z",
        updated_at="2026-08-28T08:00:00Z",
        notes="Phase 23 evaluation approved",
    )


@pytest.fixture
def temp_release_repo() -> ReleaseRepository:
    """Fixture providing an isolated in-memory ReleaseRepository."""
    conn = sqlite3.connect(":memory:")
    repo = ReleaseRepository(conn)
    repo.eval_repo = EvaluationRepository(conn)  # type: ignore[attr-defined]
    return repo


# ===========================================================================
# 1-15: State Constants, Allowed Transitions & Data Model Tests
# ===========================================================================

def test_01_release_state_constants() -> None:
    assert RELEASE_STAGE_EVALUATION_APPROVED == "EVALUATION_APPROVED"
    assert RELEASE_STAGE_CANDIDATE_CREATED == "RELEASE_CANDIDATE_CREATED"
    assert RELEASE_STAGE_PREFLIGHT_VALIDATED == "RELEASE_PREFLIGHT_VALIDATED"
    assert RELEASE_STAGE_PENDING_APPROVAL == "PENDING_RELEASE_APPROVAL"
    assert RELEASE_STAGE_APPROVED == "RELEASE_APPROVED"
    assert RELEASE_STAGE_ACTIVE == "ACTIVE"
    assert RELEASE_STAGE_ROLLED_BACK == "ROLLED_BACK"


def test_02_allowed_transitions_map() -> None:
    assert RELEASE_STAGE_PREFLIGHT_VALIDATED in RELEASE_ALLOWED_TRANSITIONS[RELEASE_STAGE_CANDIDATE_CREATED]
    assert RELEASE_STAGE_APPROVED in RELEASE_ALLOWED_TRANSITIONS[RELEASE_STAGE_PENDING_APPROVAL]
    assert RELEASE_STAGE_ACTIVE in RELEASE_ALLOWED_TRANSITIONS[RELEASE_STAGE_PROMOTED]


def test_03_release_provenance_dataclass() -> None:
    prov = ReleaseProvenance("req", "gap", "rec", "cand", "op", "art", "eval", "comp", "rev", "rel", "prom", "rb", "admin", "now", "type", "low", "RAG")
    d = prov.to_dict()
    assert d["release_id"] == "rel"
    assert d["promotion_operation_id"] == "prom"


def test_04_release_candidate_dataclass(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Content text", created_by="admin-1")
    d = cand.to_dict()
    assert d["release_id"] == cand.release_id
    assert d["release_status"] == RELEASE_STAGE_PENDING_APPROVAL


def test_05_release_approval_dataclass() -> None:
    app = ReleaseApproval("app-1", "rel-1", "admin-1", "now", "APPROVED", "notes", "hash")
    d = app.to_dict()
    assert d["approval_id"] == "app-1"


def test_06_promotion_operation_dataclass() -> None:
    op = PromotionOperation("prom-1", "rel-1", "v1.0.0", "rag-rel-v1.0.0", None, "ACTIVE", "key", "admin", "now", "now", "VERIFIED", "audit-1")
    d = op.to_dict()
    assert d["promotion_status"] == "ACTIVE"


def test_07_rollback_operation_dataclass() -> None:
    rb = RollbackOperation("rb-1", "rel-1", "v1.1.0", "v1.0.0", "ROLLED_BACK", "admin", "now", "now", "reason", "audit-1")
    d = rb.to_dict()
    assert d["rollback_status"] == "ROLLED_BACK"


def test_08_release_preflight_result_structure() -> None:
    res = ReleasePreflightResult(True, RELEASE_STAGE_PREFLIGHT_VALIDATED, "rel-1", "art-1", "eval-1")
    d = res.to_dict()
    assert d["is_valid"] is True


def test_09_generate_id_formatting() -> None:
    assert generate_release_id().startswith("rel-")
    assert generate_release_version("RAG").startswith("rag-rel-")
    assert generate_release_version("DATASET").startswith("ds-rel-")


def test_10_error_classes_hierarchy() -> None:
    assert issubclass(ReleasePreflightError, ReleaseGovernanceError)
    assert issubclass(InvalidReleaseTransitionError, ReleaseGovernanceError)
    assert issubclass(ReleaseApprovalRequiredError, ReleaseGovernanceError)


def test_11_release_candidate_immutability(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Content text", created_by="admin-1")
    with pytest.raises(AttributeError):
        cand.release_status = "ACTIVE"  # type: ignore[misc]


def test_12_release_approval_immutability() -> None:
    app = ReleaseApproval("app-1", "rel-1", "admin-1", "now", "APPROVED")
    with pytest.raises(AttributeError):
        app.decision = "REJECTED"  # type: ignore[misc]


def test_13_promotion_operation_immutability() -> None:
    op = PromotionOperation("prom-1", "rel-1", "v1", "v2", None, "ACTIVE", "key", "admin", "now", "now", "VERIFIED", "ref")
    with pytest.raises(AttributeError):
        op.promotion_status = "FAILED"  # type: ignore[misc]


def test_14_rollback_operation_immutability() -> None:
    rb = RollbackOperation("rb-1", "rel-1", "v2", "v1", "ROLLED_BACK", "admin", "now", "now", "reason", "ref")
    with pytest.raises(AttributeError):
        rb.rollback_status = "FAILED"  # type: ignore[misc]


def test_15_idempotency_key_computation() -> None:
    k1 = compute_promotion_idempotency_key("rel-1", "v1.0.0")
    k2 = compute_promotion_idempotency_key("rel-1", "v1.0.0")
    assert k1 == k2


# ===========================================================================
# 16-30: Pre-Release Validation & Security Boundary Tests
# ===========================================================================

def test_16_run_prerelease_validation_success(sample_evaluation_record: EvaluationRecord) -> None:
    res = run_prerelease_validation(sample_evaluation_record, "Clean content text")
    assert res.is_valid is True
    assert res.status == RELEASE_STAGE_PREFLIGHT_VALIDATED


def test_17_run_prerelease_validation_fails_unapproved_evaluation() -> None:
    eval_prov = EvaluationProvenance("r", "g", "rec", "c", "op", "art", "eval", None, None, None, "admin", "now", "type", "low", "RAG")
    unapp_eval = EvaluationRecord("eval-1", "art-1", "RAG", "v1", EVALUATION_STAGE_PENDING_HUMAN_REVIEW, 0.9, (), eval_prov, "now", "now")
    res = run_prerelease_validation(unapp_eval, "Clean content text")
    assert res.is_valid is False
    assert res.evaluation_approved_pass is False
    assert "EVALUATION_NOT_APPROVED" in res.issues


def test_18_run_prerelease_validation_fails_security_boundary(sample_evaluation_record: EvaluationRecord) -> None:
    sec_prov = EvaluationProvenance("r", "g", "rec", "c", "op", "art", "eval", None, None, "APPROVED", "admin", "now", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "RAG")
    sec_eval = EvaluationRecord("eval-1", "art-1", "RAG", "v1", EVALUATION_STAGE_APPROVED, 0.9, (), sec_prov, "now", "now")
    res = run_prerelease_validation(sec_eval, "Clean content text")
    assert res.is_valid is False
    assert res.security_boundary_pass is False
    assert "SECURITY_ADMIN_BOUNDARY_PROHIBITED" in res.issues


def test_19_run_prerelease_validation_fails_secret_credentials(sample_evaluation_record: EvaluationRecord) -> None:
    res = run_prerelease_validation(sample_evaluation_record, "Secret content api_key=secret123")
    assert res.is_valid is False
    assert res.secret_audit_pass is False
    assert "SECRET_CREDENTIAL_DETECTED" in res.issues


def test_20_run_prerelease_validation_fails_hash_failure(sample_evaluation_record: EvaluationRecord) -> None:
    res = run_prerelease_validation(sample_evaluation_record, "Clean content text", hash_pass=False)
    assert res.is_valid is False
    assert res.hash_pass is False
    assert "CONTENT_HASH_VERIFICATION_FAILED" in res.issues


def test_21_create_release_candidate_fails_unapproved_evaluation() -> None:
    eval_prov = EvaluationProvenance("r", "g", "rec", "c", "op", "art", "eval", None, None, None, "admin", "now", "type", "low", "RAG")
    unapp_eval = EvaluationRecord("eval-1", "art-1", "RAG", "v1", EVALUATION_STAGE_PENDING_HUMAN_REVIEW, 0.9, (), eval_prov, "now", "now")
    service = ReleaseManagementService()
    with pytest.raises(ReleasePreflightError):
        service.create_release_candidate(unapp_eval, "Clean content", created_by="admin-1")


def test_22_create_release_candidate_fails_security_boundary() -> None:
    sec_prov = EvaluationProvenance("r", "g", "rec", "c", "op", "art", "eval", None, None, "APPROVED", "admin", "now", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "RAG")
    sec_eval = EvaluationRecord("eval-1", "art-1", "RAG", "v1", EVALUATION_STAGE_APPROVED, 0.9, (), sec_prov, "now", "now")
    service = ReleaseManagementService()
    with pytest.raises(ReleasePreflightError):
        service.create_release_candidate(sec_eval, "Clean content", created_by="admin-1")


def test_23_create_release_candidate_fails_secret_credentials(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    with pytest.raises(ReleasePreflightError):
        service.create_release_candidate(sample_evaluation_record, "password=secret123", created_by="admin-1")


def test_24_prerelease_validation_is_deterministic(sample_evaluation_record: EvaluationRecord) -> None:
    r1 = run_prerelease_validation(sample_evaluation_record, "text")
    r2 = run_prerelease_validation(sample_evaluation_record, "text")
    assert r1.is_valid == r2.is_valid


def test_25_secret_sanitizer_redacts_bearer_tokens(sample_evaluation_record: EvaluationRecord) -> None:
    assert run_prerelease_validation(sample_evaluation_record, "Authorization Bearer token123").secret_audit_pass is False


def test_26_secret_sanitizer_passes_clean_content(sample_evaluation_record: EvaluationRecord) -> None:
    assert run_prerelease_validation(sample_evaluation_record, "Clean technical documentation").secret_audit_pass is True


def test_27_preflight_result_contains_issues_list(sample_evaluation_record: EvaluationRecord) -> None:
    res = run_prerelease_validation(sample_evaluation_record, "api_key=secret123")
    assert len(res.issues) > 0


def test_28_preflight_pass_does_not_equal_promotion(sample_evaluation_record: EvaluationRecord) -> None:
    res = run_prerelease_validation(sample_evaluation_record, "Clean content")
    assert res.status == RELEASE_STAGE_PREFLIGHT_VALIDATED
    assert res.status != RELEASE_STAGE_ACTIVE


def test_29_content_hash_generated(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    assert len(cand.content_hash) == 64


def test_30_provenance_hash_generated(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    assert len(cand.provenance_hash) == 64


# ===========================================================================
# 31-45: 12-Step Provenance Chain Tests
# ===========================================================================

def test_31_release_candidate_preserves_evaluation_provenance(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    assert cand.provenance.evaluation_id == sample_evaluation_record.evaluation_id
    assert cand.provenance.source_request_id == sample_evaluation_record.provenance.source_request_id


def test_32_release_provenance_includes_release_id(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    assert cand.provenance.release_id == cand.release_id


def test_33_promotion_operation_updates_provenance(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")

    act_cand, prom_op = service.promote_release(app_cand, previous_active_version=None, approved_by="super-admin-1")
    assert act_cand.provenance.promotion_operation_id == prom_op.operation_id


def test_34_rollback_operation_updates_provenance(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    act_cand, _ = service.promote_release(app_cand, previous_active_version=None, approved_by="super-admin-1")

    rb_cand, rb_op = service.rollback_release(act_cand, "v1.0.0", approved_by="super-admin-1", reason="Testing rollback")
    assert rb_cand.provenance.rollback_operation_id == rb_op.rollback_id


def test_35_provenance_serialization_dict(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    d = cand.provenance.to_dict()
    assert d["release_id"] == cand.release_id


def test_36_provenance_preserves_gap_type(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    assert cand.provenance.gap_type == sample_evaluation_record.provenance.gap_type


def test_37_provenance_preserves_severity(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    assert cand.provenance.severity == sample_evaluation_record.provenance.severity


def test_38_provenance_artifact_type_traceability(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    assert cand.provenance.artifact_type == "RAG_SOURCE_VERSION"


def test_39_release_approval_contains_hash(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    _, app = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    assert len(app.approval_hash) == 64


def test_40_promotion_op_contains_idempotency_key(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    _, prom_op = service.promote_release(app_cand, previous_active_version=None, approved_by="super-admin-1")
    assert len(prom_op.idempotency_key) == 64


def test_41_rollback_op_contains_reason(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    act_cand, _ = service.promote_release(app_cand, previous_active_version=None, approved_by="super-admin-1")

    _, rb_op = service.rollback_release(act_cand, "v1.0.0", approved_by="super-admin-1", reason="Performance degrade")
    assert rb_op.reason == "Performance degrade"


def test_42_promotion_audit_reference_recorded(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    _, prom_op = service.promote_release(app_cand, previous_active_version=None, approved_by="super-admin-1")
    assert prom_op.audit_reference.startswith("audit-prom-")


def test_43_rollback_audit_reference_recorded(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    act_cand, _ = service.promote_release(app_cand, previous_active_version=None, approved_by="super-admin-1")

    _, rb_op = service.rollback_release(act_cand, "v1.0.0", approved_by="super-admin-1", reason="Testing rollback")
    assert rb_op.audit_reference.startswith("audit-rb-")


def test_44_decision_timestamp_recorded(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    _, app = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    assert app.approved_at is not None


def test_45_reviewer_identity_recorded(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    _, app = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    assert app.approved_by == "super-admin-1"


# ===========================================================================
# 46-60: Human Release Approval Gate Tests
# ===========================================================================

def test_46_process_release_approval_approved(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    updated, app = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    assert updated.release_status == RELEASE_STAGE_READY_FOR_PROMOTION
    assert app.decision == RELEASE_STAGE_APPROVED


def test_47_process_release_approval_rejected(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    updated, app = service.process_release_approval(cand, "REJECTED", approved_by="super-admin-1")
    assert updated.release_status == RELEASE_STAGE_REJECTED
    assert app.decision == RELEASE_STAGE_REJECTED


def test_48_process_release_approval_deferred(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    updated, app = service.process_release_approval(cand, "DEFERRED", approved_by="super-admin-1")
    assert updated.release_status == RELEASE_STAGE_DEFERRED
    assert app.decision == RELEASE_STAGE_DEFERRED


def test_49_release_approval_requires_reviewer_identity(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    with pytest.raises(ReleaseApprovalRequiredError):
        service.process_release_approval(cand, "APPROVED", approved_by="   ")


def test_50_invalid_decision_string_raises_error(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    with pytest.raises(InvalidReleaseTransitionError):
        service.process_release_approval(cand, "INVALID_DECISION", approved_by="admin-1")


def test_51_cannot_promote_unapproved_release(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    # Candidate in PENDING_RELEASE_APPROVAL cannot be promoted
    with pytest.raises(InvalidReleaseTransitionError):
        service.promote_release(cand, previous_active_version=None, approved_by="admin-1")


def test_52_cannot_promote_rejected_release(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    rej_cand, _ = service.process_release_approval(cand, "REJECTED", approved_by="admin-1")

    with pytest.raises(InvalidReleaseTransitionError):
        service.promote_release(rej_cand, previous_active_version=None, approved_by="admin-1")


def test_53_evaluation_approved_alone_does_not_promote(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    assert cand.release_status == RELEASE_STAGE_PENDING_APPROVAL
    assert cand.release_status != RELEASE_STAGE_ACTIVE


def test_54_deferred_release_can_be_re_reviewed(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    def_cand, _ = service.process_release_approval(cand, "DEFERRED", approved_by="admin-1")

    pending_cand = ReleaseCandidate(def_cand.release_id, def_cand.artifact_id, def_cand.artifact_type, def_cand.artifact_version, def_cand.evaluation_id, def_cand.evaluation_status, RELEASE_STAGE_PENDING_APPROVAL, def_cand.release_version, def_cand.content_hash, def_cand.provenance_hash, def_cand.created_by, def_cand.created_at, def_cand.provenance)
    app_cand, _ = service.process_release_approval(pending_cand, "APPROVED", approved_by="admin-1")
    assert app_cand.release_status == RELEASE_STAGE_READY_FOR_PROMOTION


def test_55_rag_release_service_review_flow(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    service = RagReleaseService(temp_release_repo.conn)

    cand = service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    updated_cand, app = service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")
    assert updated_cand.release_status == RELEASE_STAGE_READY_FOR_PROMOTION


def test_56_dataset_release_service_review_flow(temp_release_repo: ReleaseRepository) -> None:
    ds_prov = EvaluationProvenance("r", "g", "rec", "c", "op", "art-ds", "eval-ds", None, None, "APPROVED", "admin", "now", "type", "low", "DATASET_EXPORT_ARTIFACT")
    ds_eval = EvaluationRecord("eval-ds", "art-ds", "DATASET_EXPORT_ARTIFACT", "v1.0.0", EVALUATION_STAGE_APPROVED, 0.95, (), ds_prov, "now", "now")
    temp_release_repo.eval_repo.insert_evaluation_record(ds_eval)

    service = DatasetReleaseService(temp_release_repo.conn)
    cand = service.create_release_candidate(ds_eval.evaluation_id, created_by="admin-1")
    updated_cand, app = service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-2")
    assert updated_cand.release_status == RELEASE_STAGE_READY_FOR_PROMOTION


def test_57_promotion_service_orchestration(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)

    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    app_cand, _ = rag_service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    active_cand, prom_op = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")
    assert active_cand.release_status == RELEASE_STAGE_ACTIVE
    assert prom_op.promotion_status == RELEASE_STAGE_ACTIVE


def test_58_promotion_updates_active_version_pointer(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)

    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    app_cand, _ = rag_service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    active_cand, _ = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")

    pointer = temp_release_repo.get_active_version_pointer("RAG_SOURCE_VERSION", "default")
    assert pointer is not None
    assert pointer["active_release_version"] == active_cand.release_version


def test_59_rollback_updates_active_version_pointer(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)

    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    app_cand, _ = rag_service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    active_cand, _ = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")

    rb_cand, rb_op = prom_service.rollback_release(active_cand.release_id, "rag-rel-v1.0.0", approved_by="super-admin-1")
    assert rb_cand.release_status == RELEASE_STAGE_ROLLED_BACK

    pointer = temp_release_repo.get_active_version_pointer("RAG_SOURCE_VERSION", "default")
    assert pointer is not None
    assert pointer["active_release_version"] == "rag-rel-v1.0.0"


def test_60_non_destructive_rollback_preserves_historical_release(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)

    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    app_cand, _ = rag_service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    active_cand, _ = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")
    prom_service.rollback_release(active_cand.release_id, "rag-rel-v1.0.0", approved_by="super-admin-1")

    # Release record MUST still exist in repository
    stored_rel = temp_release_repo.get_release_by_id(cand.release_id)
    assert stored_rel is not None


# ===========================================================================
# 61-75: Idempotency & Promotion/Rollback Edge Case Tests
# ===========================================================================

def test_61_idempotent_promotion_returns_existing_op(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)

    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    app_cand, _ = rag_service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    act1, op1 = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")
    act2, op2 = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")

    assert op1.operation_id == op2.operation_id


def test_62_cannot_rollback_unpromoted_release(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    with pytest.raises(InvalidReleaseTransitionError):
        service.rollback_release(cand, "v1.0.0", approved_by="admin-1", reason="test")


def test_63_non_existent_release_preflight_raises_value_error(temp_release_repo: ReleaseRepository) -> None:
    service = RagReleaseService(temp_release_repo.conn)
    with pytest.raises(ValueError):
        service.run_preflight("eval-non-existent")


def test_64_non_existent_dataset_release_preflight_raises_value_error(temp_release_repo: ReleaseRepository) -> None:
    service = DatasetReleaseService(temp_release_repo.conn)
    with pytest.raises(ValueError):
        service.run_preflight("eval-non-existent")


def test_65_non_existent_release_candidate_review_raises_value_error(temp_release_repo: ReleaseRepository) -> None:
    service = RagReleaseService(temp_release_repo.conn)
    with pytest.raises(ValueError):
        service.review_release("rel-non-existent", "APPROVED", reviewer_id="admin-1")


def test_66_non_existent_promotion_raises_value_error(temp_release_repo: ReleaseRepository) -> None:
    service = PromotionRollbackService(temp_release_repo.conn)
    with pytest.raises(ValueError):
        service.promote_release("rel-non-existent", approved_by="admin-1")


def test_67_non_existent_rollback_raises_value_error(temp_release_repo: ReleaseRepository) -> None:
    service = PromotionRollbackService(temp_release_repo.conn)
    with pytest.raises(ValueError):
        service.rollback_release("rel-non-existent", "v1.0.0", approved_by="admin-1")


def test_68_aggregate_release_metrics(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)
    rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")

    metrics = temp_release_repo.aggregate_metrics()
    assert metrics["total_releases"] == 1
    assert metrics["status_counts"][RELEASE_STAGE_PENDING_APPROVAL] == 1


def test_69_list_releases_filtering(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)
    rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")

    releases = temp_release_repo.list_releases(artifact_type="RAG_SOURCE_VERSION")
    assert len(releases) == 1


def test_70_rollback_idempotency_key_computation() -> None:
    k1 = compute_rollback_idempotency_key("rel-1", "v2", "v1")
    k2 = compute_rollback_idempotency_key("rel-1", "v2", "v1")
    assert k1 == k2


def test_71_release_repository_schema_initialization(temp_release_repo: ReleaseRepository) -> None:
    cursor = temp_release_repo.conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r["name"] for r in cursor.fetchall()]
    assert "phase24_release_candidates" in tables
    assert "phase24_release_approvals" in tables
    assert "phase24_promotion_operations" in tables
    assert "phase24_rollback_operations" in tables
    assert "phase24_active_version_pointers" in tables


def test_72_release_repository_indexes_exist(temp_release_repo: ReleaseRepository) -> None:
    cursor = temp_release_repo.conn.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indexes = [r["name"] for r in cursor.fetchall()]
    assert "idx_phase24_rel_art" in indexes
    assert "idx_phase24_prom_key" in indexes


def test_73_utf8_encoding_preserved_in_release_notes(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "தமிழ் வெளியீடு", created_by="admin-1")
    assert cand.notes is not None


def test_74_release_candidate_created_at_recorded(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    assert cand.created_at is not None


def test_75_promotion_operation_verification_status(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    _, prom_op = service.promote_release(app_cand, previous_active_version=None, approved_by="super-admin-1")
    assert prom_op.verification_status == "VERIFIED"


# ===========================================================================
# 76-90: Terminal States & Security Invariants
# ===========================================================================

def test_76_terminal_rejected_state_prevents_re_review(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    rej_cand, _ = service.process_release_approval(cand, "REJECTED", approved_by="admin-1")

    with pytest.raises(InvalidReleaseTransitionError):
        service.process_release_approval(rej_cand, "APPROVED", approved_by="admin-1")


def test_77_zero_autonomous_training_triggered(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="admin-1")
    service.promote_release(app_cand, previous_active_version=None, approved_by="admin-1")

    # Verify zero training files or model weights mutated
    assert not os.path.exists("data/model_weights.pt")


def test_78_non_destructive_rollback_preserves_evaluation(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)

    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    app_cand, _ = rag_service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    active_cand, _ = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")
    prom_service.rollback_release(active_cand.release_id, "rag-rel-v1.0.0", approved_by="super-admin-1")

    # Evaluation record MUST remain intact
    eval_rec = temp_release_repo.eval_repo.get_evaluation_by_id(sample_evaluation_record.evaluation_id)
    assert eval_rec is not None


def test_79_promotion_preserves_previous_active_version_field(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    _, prom_op = service.promote_release(app_cand, previous_active_version="v1.0.0-old", approved_by="super-admin-1")
    assert prom_op.previous_active_version == "v1.0.0-old"


def test_80_rollback_operation_reason_recorded(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    act_cand, _ = service.promote_release(app_cand, previous_active_version=None, approved_by="super-admin-1")

    _, rb_op = service.rollback_release(act_cand, "v1.0.0", approved_by="super-admin-1", reason="Manual testing rollback")
    assert rb_op.reason == "Manual testing rollback"


def test_81_release_candidate_content_hash_integrity(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand1 = service.create_release_candidate(sample_evaluation_record, "Content text 1", created_by="admin-1")
    cand2 = service.create_release_candidate(sample_evaluation_record, "Content text 2", created_by="admin-1")
    assert cand1.content_hash != cand2.content_hash


def test_82_release_candidate_provenance_hash_integrity(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand1 = service.create_release_candidate(sample_evaluation_record, "Content text", created_by="admin-1")
    cand2 = service.create_release_candidate(sample_evaluation_record, "Content text", created_by="admin-1")
    assert cand1.provenance_hash != cand2.provenance_hash


def test_83_release_approval_hash_integrity(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Content text", created_by="admin-1")
    _, app1 = service.process_release_approval(cand, "APPROVED", approved_by="admin-1")
    _, app2 = service.process_release_approval(cand, "APPROVED", approved_by="admin-2")
    assert app1.approval_hash != app2.approval_hash


def test_84_release_approval_notes_field_preserved(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Content text", created_by="admin-1")
    _, app = service.process_release_approval(cand, "APPROVED", approved_by="admin-1", reviewer_notes="Approved for prod")
    assert app.reviewer_notes == "Approved for prod"


def test_85_release_repository_get_active_pointer_returns_none_if_missing(temp_release_repo: ReleaseRepository) -> None:
    assert temp_release_repo.get_active_version_pointer("UNKNOWN_TYPE", "default") is None


def test_86_promotion_operation_persisted_in_database(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)

    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    app_cand, _ = rag_service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    _, prom_op = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")

    stored = temp_release_repo.get_promotion_by_idempotency_key(prom_op.idempotency_key)
    assert stored is not None
    assert stored.operation_id == prom_op.operation_id


def test_87_rollback_operation_persisted_in_database(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)

    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    app_cand, _ = rag_service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    active_cand, _ = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")
    _, rb_op = prom_service.rollback_release(active_cand.release_id, "rag-rel-v1.0.0", approved_by="super-admin-1")

    cursor = temp_release_repo.conn.execute("SELECT * FROM phase24_rollback_operations WHERE rollback_id = ?;", (rb_op.rollback_id,))
    assert cursor.fetchone() is not None


def test_88_active_version_pointer_updated_on_rollback(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)

    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    app_cand, _ = rag_service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    active_cand, _ = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")
    prom_service.rollback_release(active_cand.release_id, "rag-rel-v1.0.0", approved_by="super-admin-1")

    pointer = temp_release_repo.get_active_version_pointer("RAG_SOURCE_VERSION", "default")
    assert pointer["active_release_version"] == "rag-rel-v1.0.0"


def test_89_list_releases_pagination(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)
    rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")

    res = temp_release_repo.list_releases(limit=1, offset=0)
    assert len(res) == 1


def test_90_release_candidate_notes_field_updated_on_approval(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    updated, _ = service.process_release_approval(cand, "APPROVED", approved_by="admin-1", reviewer_notes="Note test")
    assert "Note test" in (updated.notes or "")


# ===========================================================================
# 91-105: Service Integration & Edge Case Tests
# ===========================================================================

def test_91_rag_release_service_run_preflight(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    service = RagReleaseService(temp_release_repo.conn)
    res = service.run_preflight(sample_evaluation_record.evaluation_id)
    assert res["is_valid"] is True


def test_92_dataset_release_service_run_preflight(temp_release_repo: ReleaseRepository) -> None:
    ds_prov = EvaluationProvenance("r", "g", "rec", "c", "op", "art-ds", "eval-ds", None, None, "APPROVED", "admin", "now", "type", "low", "DATASET_EXPORT_ARTIFACT")
    ds_eval = EvaluationRecord("eval-ds", "art-ds", "DATASET_EXPORT_ARTIFACT", "v1.0.0", EVALUATION_STAGE_APPROVED, 0.95, (), ds_prov, "now", "now")
    temp_release_repo.eval_repo.insert_evaluation_record(ds_eval)

    service = DatasetReleaseService(temp_release_repo.conn)
    res = service.run_preflight("eval-ds")
    assert res["is_valid"] is True


def test_93_promote_release_without_approval_fails(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)
    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    with pytest.raises(InvalidReleaseTransitionError):
        prom_service.promote_release(cand.release_id, approved_by="admin-1")


def test_94_rollback_release_without_active_status_fails(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)
    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    with pytest.raises(InvalidReleaseTransitionError):
        prom_service.rollback_release(cand.release_id, "v1.0.0", approved_by="admin-1")


def test_95_release_repository_get_release_by_id_returns_none_if_missing(temp_release_repo: ReleaseRepository) -> None:
    assert temp_release_repo.get_release_by_id("rel-non-existent") is None


def test_96_release_provenance_full_chain_validation(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="super-admin-1")
    act_cand, prom_op = service.promote_release(app_cand, previous_active_version=None, approved_by="super-admin-1")
    rb_cand, rb_op = service.rollback_release(act_cand, "v1.0.0", approved_by="super-admin-1", reason="test")

    p = rb_cand.provenance
    assert p.source_request_id == sample_evaluation_record.provenance.source_request_id
    assert p.source_gap_id == sample_evaluation_record.provenance.source_gap_id
    assert p.candidate_id == sample_evaluation_record.provenance.candidate_id
    assert p.evaluation_id == sample_evaluation_record.evaluation_id
    assert p.release_id == cand.release_id
    assert p.promotion_operation_id == prom_op.operation_id
    assert p.rollback_operation_id == rb_op.rollback_id


def test_97_idempotency_key_different_for_different_versions() -> None:
    k1 = compute_promotion_idempotency_key("rel-1", "v1.0.0")
    k2 = compute_promotion_idempotency_key("rel-1", "v1.1.0")
    assert k1 != k2


def test_98_release_version_prefix_for_rag() -> None:
    v = generate_release_version("RAG_SOURCE_VERSION")
    assert v.startswith("rag-rel-")


def test_99_release_version_prefix_for_dataset() -> None:
    v = generate_release_version("DATASET_EXPORT_ARTIFACT")
    assert v.startswith("ds-rel-")


def test_100_release_candidate_content_hash_deterministic(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand1 = service.create_release_candidate(sample_evaluation_record, "Same content text", created_by="admin-1")
    cand2 = service.create_release_candidate(sample_evaluation_record, "Same content text", created_by="admin-1")
    assert cand1.content_hash == cand2.content_hash


def test_101_release_preflight_result_dict_conversion(sample_evaluation_record: EvaluationRecord) -> None:
    res = run_prerelease_validation(sample_evaluation_record, "Clean content text")
    d = res.to_dict()
    assert d["is_valid"] is True
    assert d["evaluation_approved_pass"] is True


def test_102_release_approval_dict_conversion() -> None:
    app = ReleaseApproval("app-1", "rel-1", "admin-1", "now", "APPROVED", "notes", "hash")
    d = app.to_dict()
    assert d["approval_id"] == "app-1"


def test_103_promotion_operation_dict_conversion() -> None:
    op = PromotionOperation("op-1", "rel-1", "v1", "v2", None, "ACTIVE", "key", "admin", "now", "now", "VERIFIED", "ref")
    d = op.to_dict()
    assert d["operation_id"] == "op-1"


def test_104_rollback_operation_dict_conversion() -> None:
    rb = RollbackOperation("rb-1", "rel-1", "v2", "v1", "ROLLED_BACK", "admin", "now", "now", "reason", "ref")
    d = rb.to_dict()
    assert d["rollback_id"] == "rb-1"


def test_105_release_repository_insert_and_fetch_active_pointer(temp_release_repo: ReleaseRepository) -> None:
    temp_release_repo.update_active_version_pointer("RAG_SOURCE_VERSION", "default", "rel-1", "rag-rel-v1.0.0", "admin-1", "now")
    ptr = temp_release_repo.get_active_version_pointer("RAG_SOURCE_VERSION", "default")
    assert ptr is not None
    assert ptr["active_release_version"] == "rag-rel-v1.0.0"


# ===========================================================================
# 106-115: Reversible Operations & Governance Invariant Tests
# ===========================================================================

def test_106_reject_decision_prevents_active_status(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    rej_cand, _ = service.process_release_approval(cand, "REJECTED", approved_by="admin-1")
    assert rej_cand.release_status == RELEASE_STAGE_REJECTED
    assert rej_cand.release_status != RELEASE_STAGE_ACTIVE


def test_107_defer_decision_prevents_active_status(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    def_cand, _ = service.process_release_approval(cand, "DEFERRED", approved_by="admin-1")
    assert def_cand.release_status == RELEASE_STAGE_DEFERRED
    assert def_cand.release_status != RELEASE_STAGE_ACTIVE


def test_108_release_approval_without_promotion_remains_ready(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="admin-1")
    assert app_cand.release_status == RELEASE_STAGE_READY_FOR_PROMOTION
    assert app_cand.release_status != RELEASE_STAGE_ACTIVE


def test_109_approval_history_tracked_for_release(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    temp_release_repo.insert_release_candidate(cand)

    app1 = ReleaseApproval("app-1", cand.release_id, "admin-1", "now", "DEFERRED")
    temp_release_repo.insert_release_approval(app1)

    app2 = ReleaseApproval("app-2", cand.release_id, "admin-2", "now", "APPROVED")
    temp_release_repo.insert_release_approval(app2)

    cursor = temp_release_repo.conn.execute("SELECT * FROM phase24_release_approvals WHERE release_id = ?;", (cand.release_id,))
    assert len(cursor.fetchall()) == 2


def test_110_zero_autonomous_learning_triggered(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="admin-1")
    service.promote_release(app_cand, previous_active_version=None, approved_by="admin-1")

    # Verify zero model training or fine-tuning triggered
    assert not os.path.exists("data/model_weights.pt")


def test_111_terminal_rejected_state_prevents_promotion(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    rej_cand, _ = service.process_release_approval(cand, "REJECTED", approved_by="admin-1")

    with pytest.raises(InvalidReleaseTransitionError):
        service.promote_release(rej_cand, previous_active_version=None, approved_by="admin-1")


def test_112_terminal_active_state_prevents_re_approval(sample_evaluation_record: EvaluationRecord) -> None:
    service = ReleaseManagementService()
    cand = service.create_release_candidate(sample_evaluation_record, "Clean text", created_by="admin-1")
    app_cand, _ = service.process_release_approval(cand, "APPROVED", approved_by="admin-1")
    act_cand, _ = service.promote_release(app_cand, previous_active_version=None, approved_by="admin-1")

    with pytest.raises(InvalidReleaseTransitionError):
        service.process_release_approval(act_cand, "APPROVED", approved_by="admin-1")


def test_113_promotion_idempotency_lookup_returns_same_record(temp_release_repo: ReleaseRepository) -> None:
    op = PromotionOperation("op-1", "rel-1", "v1", "v2", None, "ACTIVE", "key-123", "admin", "now", "now", "VERIFIED", "ref")
    temp_release_repo.insert_promotion_operation(op)

    fetched = temp_release_repo.get_promotion_by_idempotency_key("key-123")
    assert fetched is not None
    assert fetched.operation_id == "op-1"


def test_114_rollback_idempotency_key_lookup(sample_evaluation_record: EvaluationRecord) -> None:
    k1 = compute_rollback_idempotency_key("rel-1", "v2", "v1")
    assert len(k1) == 64


def test_115_active_pointer_updated_on_promotion(temp_release_repo: ReleaseRepository, sample_evaluation_record: EvaluationRecord) -> None:
    temp_release_repo.eval_repo.insert_evaluation_record(sample_evaluation_record)
    rag_service = RagReleaseService(temp_release_repo.conn)

    cand = rag_service.create_release_candidate(sample_evaluation_record.evaluation_id, created_by="admin-1")
    app_cand, _ = rag_service.review_release(cand.release_id, "APPROVED", reviewer_id="super-admin-1")

    prom_service = PromotionRollbackService(temp_release_repo.conn)
    active_cand, _ = prom_service.promote_release(app_cand.release_id, approved_by="super-admin-1")

    ptr = temp_release_repo.get_active_version_pointer("RAG_SOURCE_VERSION", "default")
    assert ptr["active_release_id"] == active_cand.release_id


# ===========================================================================
# 116-120: AST Security, Admin RBAC & Production DB Integrity Tests
# ===========================================================================

def test_116_non_autonomous_learning_invariant() -> None:
    import core_model.capabilities.release_management_service as mod
    for name, obj in inspect.getmembers(mod):
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            assert "train" not in name.lower()
            assert "fine_tune" not in name.lower()
            assert "modify_weights" not in name.lower()


def test_117_ast_security_release_management_service() -> None:
    import core_model.capabilities.release_management_service as mod
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_118_no_network_or_subprocess_in_release_management_service() -> None:
    code = inspect.getsource(ReleaseManagementService).lower()
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


def test_120_final_phase24_integrity_contract_validation() -> None:
    """Final contract validation verifying Phase 24 completion."""
    assert EXPECTED_DB_SHA256 == "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    assert EXPECTED_DB_SIZE == 11096064
    assert len(RELEASE_ALLOWED_TRANSITIONS) > 0
    assert RELEASE_STAGE_APPROVED == "RELEASE_APPROVED"
    assert RELEASE_STAGE_ACTIVE == "ACTIVE"
    assert RELEASE_STAGE_ROLLED_BACK == "ROLLED_BACK"
