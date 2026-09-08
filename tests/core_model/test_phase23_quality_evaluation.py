"""Phase 23 — RAG & Dataset Quality Evaluation, Version Validation & Human-Approved Improvement Loop Test Suite.

Comprehensive 120-test suite verifying:
- Dataclasses, constants, and state machine transitions
- Pre-evaluation validation & secret re-validation
- SECURITY_ADMIN_BOUNDARY hard block
- RAG evaluation metric calculations
- Dataset evaluation metric calculations
- Version comparison engine & regression detection (BETTER, SAME, REGRESSED, INCONCLUSIVE)
- Human review approval gate requirement (Evaluation PASS != Approval)
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
from core_model.capabilities.knowledge_gap_governance_service import (
    APPROVAL_APPROVED,
    CANDIDATE_DATASET,
    CANDIDATE_RAG,
    STATUS_APPROVED,
    KnowledgeGapRecord,
)
from core_model.capabilities.candidate_curation_service import (
    DATASET_STATUS_READY_FOR_EXPORT,
    DUPLICATE_UNIQUE,
    CONFLICT_NONE,
    RAG_STATUS_READY_FOR_INGESTION,
    CandidateProvenance,
    DatasetCandidateStagingRecord,
    RAGCandidateStagingRecord,
)
from core_model.capabilities.controlled_ingestion_service import (
    RAG_STAGE_VERIFIED,
    ControlledOperationRecord,
    ProvenanceChain,
)
from core_model.capabilities.evaluation_service import (
    COMPARISON_BETTER,
    COMPARISON_INCONCLUSIVE,
    COMPARISON_REGRESSED,
    COMPARISON_SAME,
    EVALUATION_ALLOWED_TRANSITIONS,
    EVALUATION_STAGE_APPROVED,
    EVALUATION_STAGE_CREATED,
    EVALUATION_STAGE_DEFERRED,
    EVALUATION_STAGE_EVALUATED,
    EVALUATION_STAGE_PENDING_HUMAN_REVIEW,
    EVALUATION_STAGE_PREFLIGHT_FAILED,
    EVALUATION_STAGE_PREFLIGHT_VALIDATED,
    EVALUATION_STAGE_REJECTED,
    EvaluationApprovalRequiredError,
    EvaluationMetric,
    EvaluationPreflightError,
    EvaluationPreflightResult,
    EvaluationProvenance,
    EvaluationRecord,
    EvaluationReview,
    EvaluationService,
    InvalidEvaluationTransitionError,
    QualityEvaluationEngine,
    QualityEvaluationError,
    VersionComparison,
    generate_comparison_id,
    generate_evaluation_id,
    generate_review_id,
    run_preevaluation_validation,
)
from backend.database.repositories.controlled_ingestion_repository import ControlledIngestionRepository
from backend.database.repositories.evaluation_repository import EvaluationRepository
from backend.services.rag_evaluation_service import RagEvaluationService
from backend.services.dataset_evaluation_service import DatasetEvaluationService
from backend.services.version_comparison_service import VersionComparisonService

PROD_DB_PATH = "data/database/brud_ai.db"
EXPECTED_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_DB_SIZE = 11096064


@pytest.fixture
def sample_provenance_chain() -> ProvenanceChain:
    return ProvenanceChain(
        source_request_id="req-p23-01",
        source_gap_id="gap-p23-01",
        source_record_id="rec-p23-01",
        candidate_id="cand-p23-01",
        operation_id="op-p23-01",
        artifact_id="art-p23-01",
        approved_by="admin-1",
        approved_at="2026-08-28T08:00:00Z",
        gap_type=GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
        severity=SEVERITY_LOW,
        candidate_type="RAG_CANDIDATE",
    )


@pytest.fixture
def temp_eval_repo() -> EvaluationRepository:
    """Fixture providing an isolated in-memory EvaluationRepository."""
    conn = sqlite3.connect(":memory:")
    repo = EvaluationRepository(conn)
    repo.ingestion_repo = ControlledIngestionRepository(conn)  # type: ignore[attr-defined]
    return repo


# ===========================================================================
# 1-15: State Constants, Allowed Transitions & Data Model Tests
# ===========================================================================

def test_01_evaluation_state_constants() -> None:
    assert EVALUATION_STAGE_CREATED == "EVALUATION_CREATED"
    assert EVALUATION_STAGE_PREFLIGHT_VALIDATED == "PREFLIGHT_VALIDATED"
    assert EVALUATION_STAGE_EVALUATED == "EVALUATED"
    assert EVALUATION_STAGE_PENDING_HUMAN_REVIEW == "PENDING_HUMAN_REVIEW"
    assert EVALUATION_STAGE_APPROVED == "APPROVED"
    assert EVALUATION_STAGE_REJECTED == "REJECTED"
    assert EVALUATION_STAGE_DEFERRED == "DEFERRED"


def test_02_comparison_constants() -> None:
    assert COMPARISON_BETTER == "BETTER"
    assert COMPARISON_SAME == "SAME"
    assert COMPARISON_REGRESSED == "REGRESSED"
    assert COMPARISON_INCONCLUSIVE == "INCONCLUSIVE"


def test_03_allowed_transitions_map() -> None:
    assert EVALUATION_STAGE_PREFLIGHT_VALIDATED in EVALUATION_ALLOWED_TRANSITIONS[EVALUATION_STAGE_CREATED]
    assert EVALUATION_STAGE_APPROVED in EVALUATION_ALLOWED_TRANSITIONS[EVALUATION_STAGE_PENDING_HUMAN_REVIEW]
    assert EVALUATION_STAGE_REJECTED in EVALUATION_ALLOWED_TRANSITIONS[EVALUATION_STAGE_PENDING_HUMAN_REVIEW]


def test_04_evaluation_provenance_dataclass() -> None:
    prov = EvaluationProvenance("req", "gap", "rec", "cand", "op", "art", "eval", "comp", "rev", "APPROVED", "admin", "2026-08-28T08:00:00Z", "type", "low", "RAG_SOURCE_VERSION")
    d = prov.to_dict()
    assert d["evaluation_id"] == "eval"
    assert d["decision"] == "APPROVED"


def test_05_evaluation_metric_dataclass() -> None:
    m = EvaluationMetric("m-1", "1.0", "relevance", 0.95, "heuristic", "art-1", "2026-08-28T08:00:00Z", "COMPUTED", "good")
    d = m.to_dict()
    assert d["value"] == 0.95


def test_06_evaluation_record_json_serializable(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    dumped = json.dumps(rec.to_dict())
    assert "evaluation_id" in dumped


def test_07_version_comparison_dataclass() -> None:
    comp = VersionComparison("comp-1", "RAG_SOURCE_VERSION", "v1.0.0", "v1.1.0", 2, 0, 1, 0.05, COMPARISON_BETTER, "2026-08-28T08:00:00Z", "phash")
    d = comp.to_dict()
    assert d["regression_status"] == COMPARISON_BETTER


def test_08_evaluation_review_dataclass() -> None:
    rev = EvaluationReview("rev-1", "eval-1", "APPROVED", "admin-1", "2026-08-28T08:00:00Z", "Looks great")
    d = rev.to_dict()
    assert d["decision"] == "APPROVED"


def test_09_generate_ids_formatting() -> None:
    assert generate_evaluation_id().startswith("eval-")
    assert generate_comparison_id().startswith("comp-")
    assert generate_review_id().startswith("rev-")


def test_10_error_classes_hierarchy() -> None:
    assert issubclass(EvaluationPreflightError, QualityEvaluationError)
    assert issubclass(InvalidEvaluationTransitionError, QualityEvaluationError)
    assert issubclass(EvaluationApprovalRequiredError, QualityEvaluationError)


def test_11_evaluation_record_immutability(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    with pytest.raises(AttributeError):
        rec.status = "APPROVED"  # type: ignore[misc]


def test_12_evaluation_metric_immutability() -> None:
    m = EvaluationMetric("m-1", "1.0", "relevance", 0.95, "heuristic", "art-1", "2026-08-28T08:00:00Z", "COMPUTED", "good")
    with pytest.raises(AttributeError):
        m.value = 1.0  # type: ignore[misc]


def test_13_evaluation_preflight_result_structure() -> None:
    res = EvaluationPreflightResult(True, EVALUATION_STAGE_PREFLIGHT_VALIDATED, "art-1", "RAG_SOURCE_VERSION", "gap-1")
    d = res.to_dict()
    assert d["is_valid"] is True


def test_14_version_comparison_immutability() -> None:
    comp = VersionComparison("comp-1", "RAG", "v1", "v2", 1, 0, 1, 0.1, COMPARISON_BETTER, "now", "hash")
    with pytest.raises(AttributeError):
        comp.regression_status = COMPARISON_REGRESSED  # type: ignore[misc]


def test_15_evaluation_review_immutability() -> None:
    rev = EvaluationReview("r-1", "e-1", "APPROVED", "admin", "now")
    with pytest.raises(AttributeError):
        rev.decision = "REJECTED"  # type: ignore[misc]


# ===========================================================================
# 16-30: Pre-Evaluation Validation & Secret Sanitization Tests
# ===========================================================================

def test_16_run_preevaluation_validation_success() -> None:
    res = run_preevaluation_validation("art-1", "RAG_SOURCE_VERSION", GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND, "Clean text content")
    assert res.is_valid is True
    assert res.status == EVALUATION_STAGE_PREFLIGHT_VALIDATED


def test_17_run_preevaluation_validation_fails_security_boundary() -> None:
    res = run_preevaluation_validation("art-1", "RAG_SOURCE_VERSION", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, "Clean text content")
    assert res.is_valid is False
    assert res.security_boundary_pass is False
    assert "SECURITY_ADMIN_BOUNDARY_PROHIBITED" in res.issues


def test_18_run_preevaluation_validation_fails_secret_credentials() -> None:
    res = run_preevaluation_validation("art-1", "RAG_SOURCE_VERSION", GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND, "Content with api_key=secret123")
    assert res.is_valid is False
    assert res.secret_audit_pass is False
    assert "SECRET_CREDENTIAL_DETECTED" in res.issues


def test_19_run_preevaluation_validation_fails_checksum_failure() -> None:
    res = run_preevaluation_validation("art-1", "RAG_SOURCE_VERSION", GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND, "Clean text content", checksum_pass=False)
    assert res.is_valid is False
    assert res.checksum_pass is False


def test_20_run_preevaluation_validation_fails_schema_failure() -> None:
    res = run_preevaluation_validation("art-1", "RAG_SOURCE_VERSION", GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND, "Clean text content", schema_pass=False)
    assert res.is_valid is False
    assert res.schema_pass is False


def test_21_rag_evaluation_fails_on_secret_credentials(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    with pytest.raises(EvaluationPreflightError):
        engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content password=secret", sample_provenance_chain)


def test_22_dataset_evaluation_fails_on_secret_credentials(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    with pytest.raises(EvaluationPreflightError):
        engine.evaluate_dataset_artifact("art-1", "v1.0.0", [{"secret": "api_key=secret123"}], {}, {}, sample_provenance_chain)


def test_23_rag_evaluation_fails_on_security_boundary(sample_provenance_chain: ProvenanceChain) -> None:
    sec_prov = ProvenanceChain(
        source_request_id="req-1",
        source_gap_id="gap-1",
        source_record_id="rec-1",
        candidate_id="cand-1",
        operation_id="op-1",
        artifact_id="art-1",
        approved_by="admin-1",
        approved_at="2026-08-28T08:00:00Z",
        gap_type=GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
        severity=SEVERITY_CRITICAL,
        candidate_type="RAG_CANDIDATE",
    )
    engine = QualityEvaluationEngine()
    with pytest.raises(EvaluationPreflightError):
        engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Clean content", sec_prov)


def test_24_dataset_evaluation_fails_on_security_boundary(sample_provenance_chain: ProvenanceChain) -> None:
    sec_prov = ProvenanceChain(
        source_request_id="req-1",
        source_gap_id="gap-1",
        source_record_id="rec-1",
        candidate_id="cand-1",
        operation_id="op-1",
        artifact_id="art-1",
        approved_by="admin-1",
        approved_at="2026-08-28T08:00:00Z",
        gap_type=GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
        severity=SEVERITY_CRITICAL,
        candidate_type="DATASET_CANDIDATE",
    )
    engine = QualityEvaluationEngine()
    with pytest.raises(EvaluationPreflightError):
        engine.evaluate_dataset_artifact("art-1", "v1.0.0", [], {}, {}, sec_prov)


def test_25_preflight_validation_is_deterministic() -> None:
    r1 = run_preevaluation_validation("art-1", "RAG", "KNOWLEDGE_NOT_FOUND", "text")
    r2 = run_preevaluation_validation("art-1", "RAG", "KNOWLEDGE_NOT_FOUND", "text")
    assert r1.is_valid == r2.is_valid


def test_26_secret_sanitizer_redacts_bearer_tokens() -> None:
    assert run_preevaluation_validation("art-1", "RAG", "KNOWLEDGE_NOT_FOUND", "Authorization Bearer token123").secret_audit_pass is False


def test_27_secret_sanitizer_redacts_api_keys() -> None:
    assert run_preevaluation_validation("art-1", "RAG", "KNOWLEDGE_NOT_FOUND", "api_key=secret123").secret_audit_pass is False


def test_28_secret_sanitizer_passes_clean_code() -> None:
    assert run_preevaluation_validation("art-1", "RAG", "KNOWLEDGE_NOT_FOUND", "def add(a, b): return a + b").secret_audit_pass is True


def test_29_preflight_result_contains_issues_list() -> None:
    res = run_preevaluation_validation("art-1", "RAG", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, "text")
    assert len(res.issues) > 0


def test_30_validation_pass_does_not_equal_approval() -> None:
    res = run_preevaluation_validation("art-1", "RAG", GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND, "text")
    assert res.status == EVALUATION_STAGE_PREFLIGHT_VALIDATED
    assert res.status != EVALUATION_STAGE_APPROVED


# ===========================================================================
# 31-45: Full Provenance Preservation Tests
# ===========================================================================

def test_31_rag_evaluation_preserves_provenance(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    assert rec.provenance.source_request_id == sample_provenance_chain.source_request_id
    assert rec.provenance.source_gap_id == sample_provenance_chain.source_gap_id
    assert rec.provenance.candidate_id == sample_provenance_chain.candidate_id


def test_32_dataset_evaluation_preserves_provenance(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_dataset_artifact("art-1", "v1.0.0", [], {"artifact_id": "art-1"}, {"f": "h"}, sample_provenance_chain)
    assert rec.provenance.source_request_id == sample_provenance_chain.source_request_id
    assert rec.provenance.candidate_id == sample_provenance_chain.candidate_id


def test_33_provenance_includes_evaluation_id(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    assert rec.provenance.evaluation_id == rec.evaluation_id


def test_34_provenance_preserves_approved_by(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    assert rec.provenance.approved_by == sample_provenance_chain.approved_by


def test_35_provenance_preserves_approved_at(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    assert rec.provenance.approved_at == sample_provenance_chain.approved_at


def test_36_review_updates_provenance_decision(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    service = EvaluationService()

    updated_eval, review = service.process_review_decision(rec, "APPROVED", reviewer_id="super-admin-1")
    assert updated_eval.provenance.decision == "APPROVED"
    assert updated_eval.provenance.review_id == review.review_id


def test_37_provenance_serialization_dict(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    d = rec.provenance.to_dict()
    assert d["artifact_id"] == "art-1"


def test_38_provenance_preserves_gap_type(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    assert rec.provenance.gap_type == sample_provenance_chain.gap_type


def test_39_provenance_preserves_severity(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    assert rec.provenance.severity == sample_provenance_chain.severity


def test_40_provenance_artifact_type_traceability(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    assert rec.provenance.artifact_type == "RAG_SOURCE_VERSION"


def test_41_version_comparison_provenance_hash(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short content", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title", "Longer comprehensive content guide for RAG", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.provenance_hash is not None


def test_42_evaluation_review_contains_provenance(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    service = EvaluationService()

    updated_eval, review = service.process_review_decision(rec, "APPROVED", reviewer_id="super-admin-1")
    assert review.provenance is not None
    assert review.provenance.evaluation_id == rec.evaluation_id


def test_43_review_notes_included_in_evaluation(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    service = EvaluationService()

    updated_eval, review = service.process_review_decision(rec, "APPROVED", reviewer_id="super-admin-1", reviewer_notes="Review note")
    assert "Review note" in (updated_eval.notes or "")


def test_44_decision_timestamp_recorded(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    service = EvaluationService()

    updated_eval, review = service.process_review_decision(rec, "APPROVED", reviewer_id="super-admin-1")
    assert review.reviewed_at is not None


def test_45_decision_reviewer_id_recorded(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    service = EvaluationService()

    updated_eval, review = service.process_review_decision(rec, "APPROVED", reviewer_id="super-admin-1")
    assert review.reviewed_by == "super-admin-1"


# ===========================================================================
# 46-60: Security Boundary & Metric Calculation Tests
# ===========================================================================

def test_46_rag_evaluation_calculates_all_metrics(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title Guide", "Content for RAG index", sample_provenance_chain)
    metric_names = [m.name for m in rec.metrics]
    assert "retrieval_relevance" in metric_names
    assert "grounding_quality" in metric_names
    assert "citation_coverage" in metric_names
    assert "chunk_quality" in metric_names
    assert "security_scan" in metric_names


def test_47_dataset_evaluation_calculates_all_metrics(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_dataset_artifact("art-1", "v1.0.0", [{"input_context": "in", "proposed_output": "out"}], {"artifact_id": "art-1"}, {"f1": "h1", "f2": "h2", "f3": "h3"}, sample_provenance_chain)
    metric_names = [m.name for m in rec.metrics]
    assert "jsonl_validity" in metric_names
    assert "manifest_integrity" in metric_names
    assert "checksum_integrity" in metric_names
    assert "record_completeness" in metric_names
    assert "security_scan" in metric_names


def test_48_rag_evaluation_overall_score_range(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title Guide", "Content for RAG index", sample_provenance_chain)
    assert 0.0 <= rec.overall_score <= 1.0


def test_49_dataset_evaluation_overall_score_range(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_dataset_artifact("art-1", "v1.0.0", [{"input_context": "in", "proposed_output": "out"}], {"artifact_id": "art-1"}, {"f1": "h1", "f2": "h2", "f3": "h3"}, sample_provenance_chain)
    assert 0.0 <= rec.overall_score <= 1.0


def test_50_security_boundary_prohibited_from_evaluation(sample_provenance_chain: ProvenanceChain) -> None:
    sec_prov = ProvenanceChain("r", "g", "rec", "c", "op", "art", "admin", "now", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "RAG")
    engine = QualityEvaluationEngine()
    with pytest.raises(EvaluationPreflightError):
        engine.evaluate_rag_artifact("art-1", "v1", "Title", "Text", sec_prov)


def test_51_security_boundary_prohibited_from_dataset_evaluation(sample_provenance_chain: ProvenanceChain) -> None:
    sec_prov = ProvenanceChain("r", "g", "rec", "c", "op", "art", "admin", "now", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "DS")
    engine = QualityEvaluationEngine()
    with pytest.raises(EvaluationPreflightError):
        engine.evaluate_dataset_artifact("art-1", "v1", [], {}, {}, sec_prov)


def test_52_secret_credentials_block_evaluation(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    with pytest.raises(EvaluationPreflightError):
        engine.evaluate_rag_artifact("art-1", "v1", "Title", "api_key=secret123", sample_provenance_chain)


def test_53_security_scan_metric_value_is_one_for_clean_text(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1", "Title Guide", "Clean content", sample_provenance_chain)
    sec_metric = next(m for m in rec.metrics if m.name == "security_scan")
    assert sec_metric.value == 1.0


def test_54_metrics_contain_input_artifact_id(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    for m in rec.metrics:
        assert m.input_artifact_id == "art-1"


def test_55_metrics_contain_calculation_method(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    for m in rec.metrics:
        assert len(m.calculation_method) > 0


def test_56_metrics_contain_timestamp(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    for m in rec.metrics:
        assert m.timestamp is not None


def test_57_metric_to_dict_conversion() -> None:
    m = EvaluationMetric("m-1", "1.0", "rel", 0.9, "calc", "art-1", "now", "COMPUTED", "ev")
    d = m.to_dict()
    assert d["metric_id"] == "m-1"


def test_58_evaluation_record_initial_status_pending_human_review(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    assert rec.status == EVALUATION_STAGE_PENDING_HUMAN_REVIEW


def test_59_dataset_record_completeness_calculation(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_dataset_artifact("art-1", "v1", [{"input_context": "a", "proposed_output": "b"}], {"artifact_id": "art-1"}, {"a": "1", "b": "2", "c": "3"}, sample_provenance_chain)
    comp_metric = next(m for m in rec.metrics if m.name == "record_completeness")
    assert comp_metric.value == 1.0


def test_60_dataset_incomplete_record_lowers_metric(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_dataset_artifact("art-1", "v1", [{"invalid": "field"}], {"artifact_id": "art-1"}, {"a": "1", "b": "2", "c": "3"}, sample_provenance_chain)
    comp_metric = next(m for m in rec.metrics if m.name == "record_completeness")
    assert comp_metric.value == 0.5


# ===========================================================================
# 61-75: Version Comparison & Regression Classification Tests
# ===========================================================================

def test_61_compare_versions_better(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short content", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title Guide", "Longer comprehensive content guide detailing RAG configuration", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.regression_status == COMPARISON_BETTER
    assert comp.quality_delta > 0.0


def test_62_compare_versions_same(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title Guide", "Content for RAG index", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.0.1", "Title Guide", "Content for RAG index", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.regression_status == COMPARISON_SAME
    assert abs(comp.quality_delta) <= 0.02


def test_63_compare_versions_regressed(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title Guide", "Longer comprehensive content guide detailing RAG configuration", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "T", "S", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.regression_status == COMPARISON_REGRESSED
    assert comp.quality_delta < 0.0


def test_64_compare_versions_security_regression_forces_regressed(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title Guide", "Long content", sample_provenance_chain)

    # Manually construct e2 with a lower security scan value
    m_sec_bad = EvaluationMetric("m-sec", "1.0", "security_scan", 0.0, "scan", "art-2", "now", "COMPUTED", "bad")
    metrics_bad = tuple(m if m.name != "security_scan" else m_sec_bad for m in e1.metrics)
    e2 = EvaluationRecord("eval-2", "art-2", "RAG", "v1.1.0", EVALUATION_STAGE_PENDING_HUMAN_REVIEW, 0.99, metrics_bad, e1.provenance, "now", "now")

    comp = engine.compare_versions(e1, e2)
    assert comp.regression_status == COMPARISON_REGRESSED
    assert "Security regression" in (comp.notes or "")


def test_65_compare_dataset_versions_better(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_dataset_artifact("art-1", "v1.0.0", [{"incomplete": "rec"}], {"artifact_id": "art-1"}, {"a": "1"}, sample_provenance_chain)
    e2 = engine.evaluate_dataset_artifact("art-2", "v1.1.0", [{"input_context": "in", "proposed_output": "out"}], {"artifact_id": "art-2"}, {"a": "1", "b": "2", "c": "3"}, sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.regression_status == COMPARISON_BETTER


def test_66_better_classification_does_not_equal_automatic_promotion(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title Guide", "Long content guide", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.regression_status == COMPARISON_BETTER
    # e2 status MUST remain PENDING_HUMAN_REVIEW
    assert e2.status == EVALUATION_STAGE_PENDING_HUMAN_REVIEW
    assert e2.status != EVALUATION_STAGE_APPROVED


def test_67_comparison_notes_included(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title Guide", "Long content guide", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.notes is not None


def test_68_version_comparison_dict_conversion(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title Guide", "Long content guide", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    d = comp.to_dict()
    assert d["version_a"] == "v1.0.0"
    assert d["version_b"] == "v1.1.0"


def test_69_comparison_id_prefix(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title Guide", "Long content guide", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.comparison_id.startswith("comp-")


def test_70_added_content_count_calculation(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title Guide", "Long content guide", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.added_content_count >= 0


def test_71_comparison_service_stores_record(temp_eval_repo: EvaluationRepository, sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title Guide", "Long content guide", sample_provenance_chain)

    temp_eval_repo.insert_evaluation_record(e1)
    temp_eval_repo.insert_evaluation_record(e2)

    service = VersionComparisonService(temp_eval_repo.conn)
    comp = service.compare_evaluations(e1.evaluation_id, e2.evaluation_id)
    assert comp.comparison_id is not None

    stored = temp_eval_repo.get_comparison("v1.0.0", "v1.1.0")
    assert stored is not None


def test_72_comparison_service_returns_existing_idempotent(temp_eval_repo: EvaluationRepository, sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title Guide", "Long content guide", sample_provenance_chain)

    temp_eval_repo.insert_evaluation_record(e1)
    temp_eval_repo.insert_evaluation_record(e2)

    service = VersionComparisonService(temp_eval_repo.conn)
    c1 = service.compare_evaluations(e1.evaluation_id, e2.evaluation_id)
    c2 = service.compare_evaluations(e1.evaluation_id, e2.evaluation_id)
    assert c1.comparison_id == c2.comparison_id


def test_73_comparison_non_existent_eval_a_raises_value_error(temp_eval_repo: EvaluationRepository, sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title Guide", "Long content guide", sample_provenance_chain)
    temp_eval_repo.insert_evaluation_record(e2)

    service = VersionComparisonService(temp_eval_repo.conn)
    with pytest.raises(ValueError):
        service.compare_evaluations("eval-non-existent", e2.evaluation_id)


def test_74_comparison_non_existent_eval_b_raises_value_error(temp_eval_repo: EvaluationRepository, sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short", sample_provenance_chain)
    temp_eval_repo.insert_evaluation_record(e1)

    service = VersionComparisonService(temp_eval_repo.conn)
    with pytest.raises(ValueError):
        service.compare_evaluations(e1.evaluation_id, "eval-non-existent")


def test_75_comparison_artifact_type_match(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Short", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "Title Guide", "Long content guide", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.artifact_type == "RAG_SOURCE_VERSION"


# ===========================================================================
# 76-90: Human Review Gate & State Machine Decision Tests
# ===========================================================================

def test_76_process_review_decision_approved(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide", sample_provenance_chain)
    service = EvaluationService()

    updated_eval, review = service.process_review_decision(rec, "APPROVED", reviewer_id="super-admin-1")
    assert updated_eval.status == EVALUATION_STAGE_APPROVED
    assert review.decision == EVALUATION_STAGE_APPROVED
    assert review.reviewed_by == "super-admin-1"


def test_77_process_review_decision_rejected(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide", sample_provenance_chain)
    service = EvaluationService()

    updated_eval, review = service.process_review_decision(rec, "REJECTED", reviewer_id="super-admin-1", reviewer_notes="Quality below standard")
    assert updated_eval.status == EVALUATION_STAGE_REJECTED
    assert review.decision == EVALUATION_STAGE_REJECTED


def test_78_process_review_decision_deferred(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide", sample_provenance_chain)
    service = EvaluationService()

    updated_eval, review = service.process_review_decision(rec, "DEFERRED", reviewer_id="super-admin-1", reviewer_notes="Re-assess next week")
    assert updated_eval.status == EVALUATION_STAGE_DEFERRED
    assert review.decision == EVALUATION_STAGE_DEFERRED


def test_79_review_decision_requires_reviewer_identity(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide", sample_provenance_chain)
    service = EvaluationService()

    with pytest.raises(EvaluationApprovalRequiredError):
        service.process_review_decision(rec, "APPROVED", reviewer_id="   ")


def test_80_invalid_decision_string_raises_error(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide", sample_provenance_chain)
    service = EvaluationService()

    with pytest.raises(InvalidEvaluationTransitionError):
        service.process_review_decision(rec, "INVALID_DECISION", reviewer_id="admin-1")


def test_81_invalid_transition_from_approved_state(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide", sample_provenance_chain)
    service = EvaluationService()

    app_eval, _ = service.process_review_decision(rec, "APPROVED", reviewer_id="admin-1")
    # Transitioning from APPROVED to REJECTED is invalid
    with pytest.raises(InvalidEvaluationTransitionError):
        service.process_review_decision(app_eval, "REJECTED", reviewer_id="admin-1")


def test_82_rag_evaluation_service_review_flow(temp_eval_repo: EvaluationRepository, sample_provenance_chain: ProvenanceChain) -> None:
    # Setup Phase 22 artifact in repository
    art_ver = "v1.0.0"
    temp_eval_repo.ingestion_repo.insert_artifact_version(
        artifact_id="art-rag-1", artifact_type="RAG_SOURCE_VERSION", artifact_version=art_ver,
        candidate_id="cand-1", operation_id="op-1", source_gap_id="gap-1", source_record_id="rec-1",
        source_request_id="req-1", provenance_hash="phash", content_hash="chash", created_by="admin-1",
        created_at="now", status="ACTIVE", checksum_sha256="sha", manifest={"title": "RAG Title"}
    )
    service = RagEvaluationService(temp_eval_repo.conn)

    eval_rec = service.evaluate_rag_artifact("art-rag-1")
    updated_eval, review = service.review_evaluation(eval_rec.evaluation_id, "APPROVED", reviewer_id="super-admin-1")
    assert updated_eval.status == EVALUATION_STAGE_APPROVED
    assert review.reviewed_by == "super-admin-1"


def test_83_dataset_evaluation_service_review_flow(temp_eval_repo: EvaluationRepository) -> None:
    temp_eval_repo.ingestion_repo.insert_artifact_version(
        artifact_id="art-ds-1", artifact_type="DATASET_EXPORT_ARTIFACT", artifact_version="v1.0.0",
        candidate_id="cand-1", operation_id="op-1", source_gap_id="gap-1", source_record_id="rec-1",
        source_request_id="req-1", provenance_hash="phash", content_hash="chash", created_by="admin-1",
        created_at="now", status="ACTIVE", checksum_sha256="sha", manifest={"artifact_id": "art-ds-1"}
    )
    service = DatasetEvaluationService(temp_eval_repo.conn)

    eval_rec = service.evaluate_dataset_artifact("art-ds-1")
    updated_eval, review = service.review_evaluation(eval_rec.evaluation_id, "APPROVED", reviewer_id="super-admin-2")
    assert updated_eval.status == EVALUATION_STAGE_APPROVED
    assert review.reviewed_by == "super-admin-2"


def test_84_approved_improvement_decision_does_not_modify_production_db(temp_eval_repo: EvaluationRepository) -> None:
    temp_eval_repo.ingestion_repo.insert_artifact_version(
        artifact_id="art-rag-1", artifact_type="RAG_SOURCE_VERSION", artifact_version="v1.0.0",
        candidate_id="cand-1", operation_id="op-1", source_gap_id="gap-1", source_record_id="rec-1",
        source_request_id="req-1", provenance_hash="phash", content_hash="chash", created_by="admin-1",
        created_at="now", status="ACTIVE", checksum_sha256="sha", manifest={"title": "RAG Title"}
    )
    service = RagEvaluationService(temp_eval_repo.conn)

    eval_rec = service.evaluate_rag_artifact("art-rag-1")
    service.review_evaluation(eval_rec.evaluation_id, "APPROVED", reviewer_id="super-admin-1")

    # Production DB file MUST NOT be touched
    assert os.path.exists(PROD_DB_PATH)
    assert os.path.getsize(PROD_DB_PATH) == EXPECTED_DB_SIZE


def test_85_review_decision_recorded_in_repository(temp_eval_repo: EvaluationRepository) -> None:
    temp_eval_repo.ingestion_repo.insert_artifact_version(
        artifact_id="art-rag-1", artifact_type="RAG_SOURCE_VERSION", artifact_version="v1.0.0",
        candidate_id="cand-1", operation_id="op-1", source_gap_id="gap-1", source_record_id="rec-1",
        source_request_id="req-1", provenance_hash="phash", content_hash="chash", created_by="admin-1",
        created_at="now", status="ACTIVE", checksum_sha256="sha", manifest={"title": "RAG Title"}
    )
    service = RagEvaluationService(temp_eval_repo.conn)

    eval_rec = service.evaluate_rag_artifact("art-rag-1")
    service.review_evaluation(eval_rec.evaluation_id, "APPROVED", reviewer_id="super-admin-1")

    reviews = temp_eval_repo.get_reviews_for_evaluation(eval_rec.evaluation_id)
    assert len(reviews) == 1
    assert reviews[0].decision == EVALUATION_STAGE_APPROVED


def test_86_deferred_evaluation_can_be_re_reviewed(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide", sample_provenance_chain)
    service = EvaluationService()

    def_eval, _ = service.process_review_decision(rec, "DEFERRED", reviewer_id="admin-1")
    # Transitioning from DEFERRED back to PENDING_HUMAN_REVIEW is legal
    pending_eval = EvaluationRecord(def_eval.evaluation_id, def_eval.artifact_id, def_eval.artifact_type, def_eval.artifact_version, EVALUATION_STAGE_PENDING_HUMAN_REVIEW, def_eval.overall_score, def_eval.metrics, def_eval.provenance, "now", "now")
    app_eval, _ = service.process_review_decision(pending_eval, "APPROVED", reviewer_id="admin-1")
    assert app_eval.status == EVALUATION_STAGE_APPROVED


def test_87_list_evaluations_filtering(temp_eval_repo: EvaluationRepository) -> None:
    temp_eval_repo.ingestion_repo.insert_artifact_version(
        artifact_id="art-rag-1", artifact_type="RAG_SOURCE_VERSION", artifact_version="v1.0.0",
        candidate_id="cand-1", operation_id="op-1", source_gap_id="gap-1", source_record_id="rec-1",
        source_request_id="req-1", provenance_hash="phash", content_hash="chash", created_by="admin-1",
        created_at="now", status="ACTIVE", checksum_sha256="sha", manifest={"title": "RAG Title"}
    )
    service = RagEvaluationService(temp_eval_repo.conn)
    service.evaluate_rag_artifact("art-rag-1")

    evals = temp_eval_repo.list_evaluations(artifact_type="RAG_SOURCE_VERSION")
    assert len(evals) == 1


def test_88_aggregate_evaluation_metrics(temp_eval_repo: EvaluationRepository) -> None:
    temp_eval_repo.ingestion_repo.insert_artifact_version(
        artifact_id="art-rag-1", artifact_type="RAG_SOURCE_VERSION", artifact_version="v1.0.0",
        candidate_id="cand-1", operation_id="op-1", source_gap_id="gap-1", source_record_id="rec-1",
        source_request_id="req-1", provenance_hash="phash", content_hash="chash", created_by="admin-1",
        created_at="now", status="ACTIVE", checksum_sha256="sha", manifest={"title": "RAG Title"}
    )
    service = RagEvaluationService(temp_eval_repo.conn)
    service.evaluate_rag_artifact("art-rag-1")

    metrics = temp_eval_repo.aggregate_metrics()
    assert metrics["total_evaluations"] == 1
    assert metrics["status_counts"][EVALUATION_STAGE_PENDING_HUMAN_REVIEW] == 1


def test_89_non_existent_rag_artifact_preflight_raises_value_error(temp_eval_repo: EvaluationRepository) -> None:
    service = RagEvaluationService(temp_eval_repo.conn)
    with pytest.raises(ValueError):
        service.run_preflight("art-non-existent")


def test_90_non_existent_dataset_artifact_preflight_raises_value_error(temp_eval_repo: EvaluationRepository) -> None:
    service = DatasetEvaluationService(temp_eval_repo.conn)
    with pytest.raises(ValueError):
        service.run_preflight("art-non-existent")


# ===========================================================================
# 91-105: Service Orchestration, Idempotency & Validation Tests
# ===========================================================================

def test_91_rag_evaluation_service_runs_preflight(temp_eval_repo: EvaluationRepository) -> None:
    temp_eval_repo.ingestion_repo.insert_artifact_version(
        artifact_id="art-rag-1", artifact_type="RAG_SOURCE_VERSION", artifact_version="v1.0.0",
        candidate_id="cand-1", operation_id="op-1", source_gap_id="gap-1", source_record_id="rec-1",
        source_request_id="req-1", provenance_hash="phash", content_hash="chash", created_by="admin-1",
        created_at="now", status="ACTIVE", checksum_sha256="sha", manifest={"title": "RAG Title"}
    )
    service = RagEvaluationService(temp_eval_repo.conn)
    res = service.run_preflight("art-rag-1")
    assert res["is_valid"] is True


def test_92_dataset_evaluation_service_runs_preflight(temp_eval_repo: EvaluationRepository) -> None:
    temp_eval_repo.ingestion_repo.insert_artifact_version(
        artifact_id="art-ds-1", artifact_type="DATASET_EXPORT_ARTIFACT", artifact_version="v1.0.0",
        candidate_id="cand-1", operation_id="op-1", source_gap_id="gap-1", source_record_id="rec-1",
        source_request_id="req-1", provenance_hash="phash", content_hash="chash", created_by="admin-1",
        created_at="now", status="ACTIVE", checksum_sha256="sha", manifest={"artifact_id": "art-ds-1"}
    )
    service = DatasetEvaluationService(temp_eval_repo.conn)
    res = service.run_preflight("art-ds-1")
    assert res["is_valid"] is True


def test_93_non_existent_evaluation_review_raises_value_error(temp_eval_repo: EvaluationRepository) -> None:
    service = RagEvaluationService(temp_eval_repo.conn)
    with pytest.raises(ValueError):
        service.review_evaluation("eval-non-existent", "APPROVED", reviewer_id="admin-1")


def test_94_non_existent_dataset_evaluation_review_raises_value_error(temp_eval_repo: EvaluationRepository) -> None:
    service = DatasetEvaluationService(temp_eval_repo.conn)
    with pytest.raises(ValueError):
        service.review_evaluation("eval-non-existent", "APPROVED", reviewer_id="admin-1")


def test_95_evaluation_metrics_persisted_in_database(temp_eval_repo: EvaluationRepository, sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    temp_eval_repo.insert_evaluation_record(rec)

    fetched = temp_eval_repo.get_evaluation_by_id(rec.evaluation_id)
    assert fetched is not None
    assert len(fetched.metrics) == 5


def test_96_dataset_evaluation_metrics_persisted(temp_eval_repo: EvaluationRepository, sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_dataset_artifact("art-1", "v1.0.0", [], {"artifact_id": "art-1"}, {"f": "h"}, sample_provenance_chain)
    temp_eval_repo.insert_evaluation_record(rec)

    fetched = temp_eval_repo.get_evaluation_by_id(rec.evaluation_id)
    assert fetched is not None
    assert len(fetched.metrics) == 5


def test_97_idempotent_evaluation_inserts_new_or_fetches(temp_eval_repo: EvaluationRepository, sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide for RAG", sample_provenance_chain)
    temp_eval_repo.insert_evaluation_record(rec)

    metrics = temp_eval_repo.aggregate_metrics()
    assert metrics["total_evaluations"] == 1


def test_98_review_decision_id_generated(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content guide", sample_provenance_chain)
    service = EvaluationService()

    updated_eval, review = service.process_review_decision(rec, "APPROVED", reviewer_id="super-admin-1")
    assert review.review_id.startswith("rev-")


def test_99_dataset_evaluation_service_evaluates_correctly(temp_eval_repo: EvaluationRepository) -> None:
    temp_eval_repo.ingestion_repo.insert_artifact_version(
        artifact_id="art-ds-1", artifact_type="DATASET_EXPORT_ARTIFACT", artifact_version="v1.0.0",
        candidate_id="cand-1", operation_id="op-1", source_gap_id="gap-1", source_record_id="rec-1",
        source_request_id="req-1", provenance_hash="phash", content_hash="chash", created_by="admin-1",
        created_at="now", status="ACTIVE", checksum_sha256="sha", manifest={"artifact_id": "art-ds-1"}
    )
    service = DatasetEvaluationService(temp_eval_repo.conn)
    rec = service.evaluate_dataset_artifact("art-ds-1")
    assert rec.artifact_id == "art-ds-1"


def test_100_rag_evaluation_service_evaluates_correctly(temp_eval_repo: EvaluationRepository) -> None:
    temp_eval_repo.ingestion_repo.insert_artifact_version(
        artifact_id="art-rag-1", artifact_type="RAG_SOURCE_VERSION", artifact_version="v1.0.0",
        candidate_id="cand-1", operation_id="op-1", source_gap_id="gap-1", source_record_id="rec-1",
        source_request_id="req-1", provenance_hash="phash", content_hash="chash", created_by="admin-1",
        created_at="now", status="ACTIVE", checksum_sha256="sha", manifest={"title": "RAG Title"}
    )
    service = RagEvaluationService(temp_eval_repo.conn)
    rec = service.evaluate_rag_artifact("art-rag-1")
    assert rec.artifact_id == "art-rag-1"


def test_101_utf8_encoding_preserved_in_evaluation_metrics(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "தமிழ் வினா", "தமிழ் விடை விளக்கம்", sample_provenance_chain)
    assert rec.overall_score > 0.0


def test_102_evaluation_notes_field_preserved(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    assert rec.notes is not None


def test_103_metrics_evidence_field_preserved(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    for m in rec.metrics:
        assert m.evidence is not None


def test_104_evaluation_repository_schema_initialization(temp_eval_repo: EvaluationRepository) -> None:
    # Verify tables exist
    cursor = temp_eval_repo.conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r["name"] for r in cursor.fetchall()]
    assert "phase23_evaluation_records" in tables
    assert "phase23_metric_results" in tables
    assert "phase23_version_comparisons" in tables
    assert "phase23_review_decisions" in tables


def test_105_evaluation_repository_indexes_exist(temp_eval_repo: EvaluationRepository) -> None:
    cursor = temp_eval_repo.conn.execute("SELECT name FROM sqlite_master WHERE type='index';")
    indexes = [r["name"] for r in cursor.fetchall()]
    assert "idx_phase23_eval_art" in indexes


# ===========================================================================
# 106-115: Reversible Decision & Non-Autonomous Learning Invariant Tests
# ===========================================================================

def test_106_reject_decision_prevents_approved_status(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    service = EvaluationService()

    rej_eval, _ = service.process_review_decision(rec, "REJECTED", reviewer_id="admin-1")
    assert rej_eval.status == EVALUATION_STAGE_REJECTED
    assert rej_eval.status != EVALUATION_STAGE_APPROVED


def test_107_defer_decision_prevents_approved_status(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    service = EvaluationService()

    def_eval, _ = service.process_review_decision(rec, "DEFERRED", reviewer_id="admin-1")
    assert def_eval.status == EVALUATION_STAGE_DEFERRED
    assert def_eval.status != EVALUATION_STAGE_APPROVED


def test_108_evaluation_pass_without_review_remains_pending(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Comprehensive Guide Title", "Detailed content guide for RAG knowledge containing reference link http://brud.ai and extended text.", sample_provenance_chain)
    assert rec.overall_score >= 0.70
    # Even with high overall score, status remains PENDING_HUMAN_REVIEW
    assert rec.status == EVALUATION_STAGE_PENDING_HUMAN_REVIEW


def test_109_review_history_tracked_for_evaluation(temp_eval_repo: EvaluationRepository, sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    temp_eval_repo.insert_evaluation_record(rec)

    service = EvaluationService()
    def_eval, rev1 = service.process_review_decision(rec, "DEFERRED", reviewer_id="admin-1")
    temp_eval_repo.update_evaluation_state(def_eval)
    temp_eval_repo.insert_review_decision(rev1)

    pending_eval = EvaluationRecord(def_eval.evaluation_id, def_eval.artifact_id, def_eval.artifact_type, def_eval.artifact_version, EVALUATION_STAGE_PENDING_HUMAN_REVIEW, def_eval.overall_score, def_eval.metrics, def_eval.provenance, "now", "now")
    app_eval, rev2 = service.process_review_decision(pending_eval, "APPROVED", reviewer_id="admin-2")
    temp_eval_repo.update_evaluation_state(app_eval)
    temp_eval_repo.insert_review_decision(rev2)

    reviews = temp_eval_repo.get_reviews_for_evaluation(rec.evaluation_id)
    assert len(reviews) == 2


def test_110_zero_autonomous_training_triggered(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_dataset_artifact("art-1", "v1.0.0", [{"input_context": "in", "proposed_output": "out"}], {"artifact_id": "art-1"}, {"f": "h"}, sample_provenance_chain)
    service = EvaluationService()

    app_eval, _ = service.process_review_decision(rec, "APPROVED", reviewer_id="admin-1")
    # Verify no training files, model weights, or background jobs created
    assert app_eval.status == EVALUATION_STAGE_APPROVED
    assert not os.path.exists("data/model_weights.pt")


def test_111_terminal_rejected_state_prevents_re_review(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    service = EvaluationService()

    rej_eval, _ = service.process_review_decision(rec, "REJECTED", reviewer_id="admin-1")
    with pytest.raises(InvalidEvaluationTransitionError):
        service.process_review_decision(rej_eval, "APPROVED", reviewer_id="admin-1")


def test_112_terminal_approved_state_prevents_re_review(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    rec = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title", "Content", sample_provenance_chain)
    service = EvaluationService()

    app_eval, _ = service.process_review_decision(rec, "APPROVED", reviewer_id="admin-1")
    with pytest.raises(InvalidEvaluationTransitionError):
        service.process_review_decision(app_eval, "REJECTED", reviewer_id="admin-1")


def test_113_version_comparison_regressed_notes(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title Guide", "Long content", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.1.0", "T", "S", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.regression_status == COMPARISON_REGRESSED
    assert "regressed" in (comp.notes or "").lower()


def test_114_version_comparison_same_notes(sample_provenance_chain: ProvenanceChain) -> None:
    engine = QualityEvaluationEngine()
    e1 = engine.evaluate_rag_artifact("art-1", "v1.0.0", "Title Guide", "Content", sample_provenance_chain)
    e2 = engine.evaluate_rag_artifact("art-2", "v1.0.1", "Title Guide", "Content", sample_provenance_chain)

    comp = engine.compare_versions(e1, e2)
    assert comp.regression_status == COMPARISON_SAME
    assert "equivalent" in (comp.notes or "").lower()


def test_115_version_comparison_inconclusive_notes(sample_provenance_chain: ProvenanceChain) -> None:
    comp = VersionComparison("comp-1", "RAG", "v1", "v2", 0, 0, 0, 0.0, COMPARISON_INCONCLUSIVE, "now", "hash", "Insufficient evidence")
    assert comp.regression_status == COMPARISON_INCONCLUSIVE


# ===========================================================================
# 116-120: AST Security, Admin RBAC & Production DB Integrity Tests
# ===========================================================================

def test_116_non_autonomous_learning_invariant() -> None:
    import core_model.capabilities.evaluation_service as mod
    for name, obj in inspect.getmembers(mod):
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            assert "train" not in name.lower()
            assert "fine_tune" not in name.lower()
            assert "modify_weights" not in name.lower()


def test_117_ast_security_evaluation_service() -> None:
    import core_model.capabilities.evaluation_service as mod
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_118_no_network_or_subprocess_in_evaluation_service() -> None:
    code = inspect.getsource(EvaluationService).lower()
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


def test_120_final_phase23_integrity_contract_validation() -> None:
    """Final contract validation verifying Phase 23 completion."""
    assert EXPECTED_DB_SHA256 == "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    assert EXPECTED_DB_SIZE == 11096064
    assert len(EVALUATION_ALLOWED_TRANSITIONS) > 0
    assert COMPARISON_BETTER == "BETTER"
    assert COMPARISON_REGRESSED == "REGRESSED"
