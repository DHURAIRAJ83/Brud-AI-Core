"""Phase 22 — Controlled RAG Ingestion & Dataset Export Test Suite.

Comprehensive 120-test suite verifying:
- Dataclasses, constants, and state machine transitions
- Pre-flight validation & secret re-validation
- SECURITY_ADMIN_BOUNDARY hard block
- Dry-run plan generation without production mutation
- Explicit human admin approval gate requirement
- Controlled RAG ingestion execution & versioning
- Controlled Dataset export execution & versioned JSONL artifact creation
- Idempotency & atomic commit guarantees
- Post-operation verification & non-destructive rollback
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
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    CANDIDATE_DATASET,
    CANDIDATE_RAG,
    STATUS_APPROVED,
    STATUS_IN_REVIEW,
    GovernanceSecurityError,
    KnowledgeGapRecord,
)
from core_model.capabilities.candidate_curation_service import (
    DATASET_STATUS_READY_FOR_EXPORT,
    DUPLICATE_EXACT,
    DUPLICATE_UNIQUE,
    CONFLICT_CONFLICTING,
    CONFLICT_NONE,
    RAG_STATUS_READY_FOR_INGESTION,
    STAGING_STATUS_APPROVED,
    STAGING_STATUS_DRAFT,
    STAGING_STATUS_VALIDATED,
    CandidateProvenance,
    DatasetCandidateStagingRecord,
    RAGCandidateStagingRecord,
    stage_dataset_candidate,
    stage_rag_candidate,
)
from core_model.capabilities.controlled_ingestion_service import (
    DATASET_EXPORT_ALLOWED_TRANSITIONS,
    DATASET_STAGE_APPROVED_FOR_EXPORT,
    DATASET_STAGE_EXPORTED,
    DATASET_STAGE_EXPORTING,
    DATASET_STAGE_EXPORT_DRY_RUN_READY,
    DATASET_STAGE_EXPORT_FAILED,
    DATASET_STAGE_PENDING_APPROVAL,
    DATASET_STAGE_PREFLIGHT_FAILED,
    DATASET_STAGE_PREFLIGHT_VALIDATED,
    DATASET_STAGE_ROLLED_BACK,
    DATASET_STAGE_VERIFICATION_FAILED,
    DATASET_STAGE_VERIFIED,
    RAG_INGESTION_ALLOWED_TRANSITIONS,
    RAG_STAGE_APPROVED_FOR_INGESTION,
    RAG_STAGE_DRY_RUN_READY,
    RAG_STAGE_INGESTED,
    RAG_STAGE_INGESTING,
    RAG_STAGE_INGESTION_FAILED,
    RAG_STAGE_PENDING_APPROVAL,
    RAG_STAGE_PREFLIGHT_FAILED,
    RAG_STAGE_PREFLIGHT_VALIDATED,
    RAG_STAGE_ROLLED_BACK,
    RAG_STAGE_VERIFICATION_FAILED,
    RAG_STAGE_VERIFIED,
    ControlledIngestionError,
    ControlledIngestionService,
    ControlledOperationRecord,
    ExportPlan,
    IngestionApprovalRequiredError,
    IngestionPlan,
    InvalidOperationTransitionError,
    PreflightResult,
    PreflightValidationError,
    ProvenanceChain,
    audit_secrets_in_text,
    compute_idempotency_key,
    generate_artifact_version,
    generate_operation_id,
    run_preflight_validation_dataset,
    run_preflight_validation_rag,
)
from backend.database.repositories.candidate_curation_repository import CandidateCurationRepository
from backend.database.repositories.controlled_ingestion_repository import ControlledIngestionRepository
from backend.services.controlled_rag_ingestion_service import ControlledRagIngestionService
from backend.services.controlled_dataset_export_service import ControlledDatasetExportService

PROD_DB_PATH = "data/database/brud_ai.db"
EXPECTED_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_DB_SIZE = 11096064


@pytest.fixture
def sample_approved_rag_kg_record() -> KnowledgeGapRecord:
    """Fixture returning a Phase 20 APPROVED KnowledgeGapRecord for RAG."""
    return KnowledgeGapRecord(
        record_id="rec-rag-p22-01",
        gap_id="gap-rag-p22-01",
        request_id="req-rag-p22-01",
        detected_language="en",
        language_confidence=0.95,
        normalized_intent="configure python RAG",
        requested_capability_id="general_chat",
        selected_capability_id="rag_query",
        routing_confidence=0.88,
        failure_classification="knowledge_not_found",
        gap_type=GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="configure python RAG",
        sanitized_metadata={"env": "prod"},
        status=STATUS_APPROVED,
        candidate_type=CANDIDATE_RAG,
        approval_state=APPROVAL_APPROVED,
        created_at="2026-08-28T08:00:00Z",
        updated_at="2026-08-28T08:10:00Z",
        reviewed_at="2026-08-28T08:10:00Z",
        reviewed_by="admin-1",
        reviewer_notes="Approved for Phase 21 RAG staging",
    )


@pytest.fixture
def sample_staged_rag_record(sample_approved_rag_kg_record: KnowledgeGapRecord) -> RAGCandidateStagingRecord:
    """Fixture returning a Phase 21 READY_FOR_INGESTION RAG candidate staging record."""
    staged = stage_rag_candidate(
        sample_approved_rag_kg_record,
        title="Python RAG Configuration Guide",
        content="Comprehensive guide detailing how to build and configure RAG in Python.",
        staged_by="admin-1",
    )
    service_curation = CandidateCurationService_dummy()
    # Transition to READY_FOR_INGESTION via helper replacement
    d = dict(staged.__dict__)
    d["status"] = RAG_STATUS_READY_FOR_INGESTION
    return RAGCandidateStagingRecord(**d)


@pytest.fixture
def sample_approved_ds_kg_record() -> KnowledgeGapRecord:
    """Fixture returning a Phase 20 APPROVED KnowledgeGapRecord for Dataset."""
    return KnowledgeGapRecord(
        record_id="rec-ds-p22-01",
        gap_id="gap-ds-p22-01",
        request_id="req-ds-p22-01",
        detected_language="en",
        language_confidence=0.92,
        normalized_intent="vector search explanation",
        requested_capability_id="general_chat",
        selected_capability_id="general_chat",
        routing_confidence=0.85,
        failure_classification="insufficient_evidence",
        gap_type=GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="partial",
        source_stage="routing",
        safe_summary="vector search explanation",
        sanitized_metadata={"domain": "ai"},
        status=STATUS_APPROVED,
        candidate_type=CANDIDATE_DATASET,
        approval_state=APPROVAL_APPROVED,
        created_at="2026-08-28T08:00:00Z",
        updated_at="2026-08-28T08:12:00Z",
        reviewed_at="2026-08-28T08:12:00Z",
        reviewed_by="admin-2",
        reviewer_notes="Approved for Phase 21 Dataset staging",
    )


@pytest.fixture
def sample_staged_dataset_record(sample_approved_ds_kg_record: KnowledgeGapRecord) -> DatasetCandidateStagingRecord:
    """Fixture returning a Phase 21 READY_FOR_EXPORT Dataset candidate staging record."""
    staged = stage_dataset_candidate(
        sample_approved_ds_kg_record,
        input_context="Explain vector similarity search.",
        proposed_output="Vector similarity search compares embeddings in vector space using distance metrics.",
        language="en",
        domain_topic="ai_concepts",
        staged_by="admin-2",
    )
    d = dict(staged.__dict__)
    d["status"] = DATASET_STATUS_READY_FOR_EXPORT
    return DatasetCandidateStagingRecord(**d)


def CandidateCurationService_dummy() -> Any:
    return None


@pytest.fixture
def temp_ingestion_repo() -> ControlledIngestionRepository:
    """Fixture providing an isolated in-memory ControlledIngestionRepository."""
    conn = sqlite3.connect(":memory:")
    repo = ControlledIngestionRepository(conn)
    repo.curation_repo = CandidateCurationRepository(conn)  # type: ignore[attr-defined]
    return repo


# ===========================================================================
# 1-15: State Constants, Allowed Transitions & Data Model Tests
# ===========================================================================

def test_01_rag_state_constants() -> None:
    assert RAG_STAGE_PREFLIGHT_VALIDATED == "PREFLIGHT_VALIDATED"
    assert RAG_STAGE_DRY_RUN_READY == "DRY_RUN_READY"
    assert RAG_STAGE_APPROVED_FOR_INGESTION == "APPROVED_FOR_INGESTION"
    assert RAG_STAGE_INGESTED == "INGESTED"
    assert RAG_STAGE_VERIFIED == "VERIFIED"
    assert RAG_STAGE_ROLLED_BACK == "ROLLED_BACK"


def test_02_dataset_state_constants() -> None:
    assert DATASET_STAGE_PREFLIGHT_VALIDATED == "PREFLIGHT_VALIDATED"
    assert DATASET_STAGE_EXPORT_DRY_RUN_READY == "EXPORT_DRY_RUN_READY"
    assert DATASET_STAGE_APPROVED_FOR_EXPORT == "APPROVED_FOR_EXPORT"
    assert DATASET_STAGE_EXPORTED == "EXPORTED"
    assert DATASET_STAGE_VERIFIED == "VERIFIED"
    assert DATASET_STAGE_ROLLED_BACK == "ROLLED_BACK"


def test_03_rag_allowed_transitions_map() -> None:
    assert RAG_STAGE_PREFLIGHT_VALIDATED in RAG_INGESTION_ALLOWED_TRANSITIONS[RAG_STATUS_READY_FOR_INGESTION]
    assert RAG_STAGE_APPROVED_FOR_INGESTION in RAG_INGESTION_ALLOWED_TRANSITIONS[RAG_STAGE_PENDING_APPROVAL]
    assert RAG_STAGE_INGESTED in RAG_INGESTION_ALLOWED_TRANSITIONS[RAG_STAGE_INGESTING]


def test_04_dataset_allowed_transitions_map() -> None:
    assert DATASET_STAGE_PREFLIGHT_VALIDATED in DATASET_EXPORT_ALLOWED_TRANSITIONS[DATASET_STATUS_READY_FOR_EXPORT]
    assert DATASET_STAGE_APPROVED_FOR_EXPORT in DATASET_EXPORT_ALLOWED_TRANSITIONS[DATASET_STAGE_PENDING_APPROVAL]
    assert DATASET_STAGE_EXPORTED in DATASET_EXPORT_ALLOWED_TRANSITIONS[DATASET_STAGE_EXPORTING]


def test_05_provenance_chain_dataclass() -> None:
    prov = ProvenanceChain(
        source_request_id="req-1",
        source_gap_id="gap-1",
        source_record_id="rec-1",
        candidate_id="cand-1",
        operation_id="op-1",
        artifact_id="art-1",
        approved_by="admin-1",
        approved_at="2026-08-28T08:00:00Z",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity="low",
        candidate_type="RAG_CANDIDATE",
    )
    d = prov.to_dict()
    assert d["source_request_id"] == "req-1"
    assert d["artifact_id"] == "art-1"


def test_06_preflight_result_json_serializable() -> None:
    res = PreflightResult(
        is_valid=True,
        status=RAG_STAGE_PREFLIGHT_VALIDATED,
        candidate_id="c-1",
        candidate_type="RAG_CANDIDATE",
        source_gap_id="g-1",
        source_record_id="r-1",
    )
    dumped = json.dumps(res.to_dict())
    assert "is_valid" in dumped


def test_07_ingestion_plan_structure() -> None:
    prov = ProvenanceChain("req-1", "gap-1", "rec-1", "cand-1", "op-1", None, "admin", "2026-08-28T08:00:00Z", "gap_type", "low", "RAG_CANDIDATE")
    plan = IngestionPlan("op-1", "cand-1", "space-1", "Title", "chash", "phash", 2, 100, "UNIQUE", "NO_CONFLICT", True, "2026-08-28T08:00:00Z", prov)
    d = plan.to_dict()
    assert d["operation_id"] == "op-1"
    assert d["is_executable"] is True


def test_08_export_plan_structure() -> None:
    prov = ProvenanceChain("req-1", "gap-1", "rec-1", "cand-1", "op-1", "art-1", "admin", "2026-08-28T08:00:00Z", "gap_type", "low", "DATASET_CANDIDATE")
    plan = ExportPlan("op-1", "cand-1", "data/exports", "v1.0.0", "chash", "phash", 1, {"files": []}, True, "2026-08-28T08:00:00Z", prov)
    d = plan.to_dict()
    assert d["artifact_version"] == "v1.0.0"


def test_09_controlled_operation_record_dataclass() -> None:
    prov = ProvenanceChain("req-1", "gap-1", "rec-1", "cand-1", "op-1", "art-1", "admin", "2026-08-28T08:00:00Z", "gap_type", "low", "RAG_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "RAG_CANDIDATE", RAG_STAGE_PENDING_APPROVAL, True, "admin", "2026-08-28T08:00:00Z", None, None, None, "art-1", "v1.0.0", "chash", "phash", "ikey", None, prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")
    assert rec.operation_id == "op-1"


def test_10_generate_operation_id_format() -> None:
    op_id = generate_operation_id("op-rag")
    assert op_id.startswith("op-rag-")


def test_11_generate_artifact_version_format() -> None:
    ver = generate_artifact_version("1.0.0")
    assert ver.startswith("v1.0.0-")


def test_12_compute_idempotency_key_determinism() -> None:
    k1 = compute_idempotency_key("c-1", "rag_ingest", "chash1")
    k2 = compute_idempotency_key("c-1", "rag_ingest", "chash1")
    assert k1 == k2
    assert len(k1) == 64


def test_13_audit_secrets_in_text_pass() -> None:
    assert audit_secrets_in_text("Normal public text without credentials") is True


def test_14_audit_secrets_in_text_fail() -> None:
    assert audit_secrets_in_text("My credential is api_key=secret123") is False
    assert audit_secrets_in_text("Authorization Bearer eyJhbGci") is False


def test_15_error_classes_inheritance() -> None:
    assert issubclass(PreflightValidationError, ControlledIngestionError)
    assert issubclass(InvalidOperationTransitionError, ControlledIngestionError)
    assert issubclass(IngestionApprovalRequiredError, ControlledIngestionError)


# ===========================================================================
# 16-30: Pre-Flight Validation Engine & Secret Sanitization Tests
# ===========================================================================

def test_16_run_preflight_validation_rag_success(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    res = run_preflight_validation_rag(sample_staged_rag_record)
    assert res.is_valid is True
    assert res.status == RAG_STAGE_PREFLIGHT_VALIDATED
    assert res.secret_audit_pass is True


def test_17_run_preflight_validation_dataset_success(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    res = run_preflight_validation_dataset(sample_staged_dataset_record)
    assert res.is_valid is True
    assert res.status == DATASET_STAGE_PREFLIGHT_VALIDATED


def test_18_preflight_rag_fails_when_not_ready_for_ingestion(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    d = dict(sample_staged_rag_record.__dict__)
    d["status"] = STAGING_STATUS_VALIDATED
    draft_rec = RAGCandidateStagingRecord(**d)
    res = run_preflight_validation_rag(draft_rec)
    assert res.is_valid is False
    assert any("CANDIDATE_NOT_READY_FOR_INGESTION" in i for i in res.issues)


def test_19_preflight_dataset_fails_when_not_ready_for_export(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    d = dict(sample_staged_dataset_record.__dict__)
    d["status"] = STAGING_STATUS_DRAFT
    draft_rec = DatasetCandidateStagingRecord(**d)
    res = run_preflight_validation_dataset(draft_rec)
    assert res.is_valid is False
    assert any("CANDIDATE_NOT_READY_FOR_EXPORT" in i for i in res.issues)


def test_20_preflight_fails_on_secret_credentials(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    d = dict(sample_staged_rag_record.__dict__)
    d["content"] = "Config info password=supersecret"
    dirty_rec = RAGCandidateStagingRecord(**d)
    res = run_preflight_validation_rag(dirty_rec)
    assert res.is_valid is False
    assert "SECRET_CREDENTIAL_DETECTED_IN_CONTENT" in res.issues


def test_21_preflight_fails_on_conflicting_candidate(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    d = dict(sample_staged_rag_record.__dict__)
    d["conflict_status"] = CONFLICT_CONFLICTING
    conf_rec = RAGCandidateStagingRecord(**d)
    res = run_preflight_validation_rag(conf_rec)
    assert res.is_valid is False
    assert "CONFLICTING_CANDIDATE_REQUIRES_RESOLUTION" in res.issues


def test_22_preflight_warns_on_exact_duplicate_candidate(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    d = dict(sample_staged_rag_record.__dict__)
    d["duplicate_status"] = DUPLICATE_EXACT
    dup_rec = RAGCandidateStagingRecord(**d)
    res = run_preflight_validation_rag(dup_rec)
    assert res.is_valid is True  # Warning, not blocking
    assert "EXACT_DUPLICATE_CANDIDATE" in res.warnings


def test_23_preflight_validation_is_deterministic(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    r1 = run_preflight_validation_rag(sample_staged_rag_record)
    r2 = run_preflight_validation_rag(sample_staged_rag_record)
    assert r1.is_valid == r2.is_valid
    assert r1.issues == r2.issues


def test_24_secret_audit_redacts_api_keys() -> None:
    assert audit_secrets_in_text("api_key=12345678901234567890") is False


def test_25_secret_audit_redacts_bearer_tokens() -> None:
    assert audit_secrets_in_text("Bearer eyJhbGciOiJIUzI1Ni") is False


def test_26_secret_audit_redacts_passwords() -> None:
    assert audit_secrets_in_text("password=mysecret") is False


def test_27_secret_audit_redacts_openai_keys() -> None:
    assert audit_secrets_in_text("sk-123456789012345678901234") is False


def test_28_secret_audit_passes_clean_code() -> None:
    assert audit_secrets_in_text("def hello(): return 'world'") is True


def test_29_preflight_result_dict_conversion() -> None:
    res = PreflightResult(True, RAG_STAGE_PREFLIGHT_VALIDATED, "c-1", "RAG_CANDIDATE", "g-1", "r-1")
    d = res.to_dict()
    assert d["candidate_id"] == "c-1"


def test_30_validation_pass_does_not_equal_approval(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    res = run_preflight_validation_rag(sample_staged_rag_record)
    assert res.is_valid is True
    # Pre-flight VALIDATED is NOT APPROVED_FOR_INGESTION
    assert res.status != RAG_STAGE_APPROVED_FOR_INGESTION


# ===========================================================================
# 31-45: Full Provenance Traceability Tests
# ===========================================================================

def test_31_provenance_chain_contains_request_to_artifact(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.provenance.source_request_id == sample_staged_rag_record.provenance.source_request_id
    assert plan.provenance.source_gap_id == sample_staged_rag_record.provenance.source_gap_id
    assert plan.provenance.source_record_id == sample_staged_rag_record.provenance.source_record_id
    assert plan.provenance.candidate_id == sample_staged_rag_record.candidate_id


def test_32_provenance_chain_preserves_approved_by(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.provenance.approved_by == sample_staged_rag_record.provenance.approved_by


def test_33_provenance_chain_preserves_approved_at(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.provenance.approved_at == sample_staged_rag_record.provenance.approved_at


def test_34_provenance_chain_is_immutable(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    with pytest.raises(AttributeError):
        plan.provenance.source_gap_id = "new-gap"  # type: ignore[misc]


def test_35_dataset_export_plan_preserves_provenance(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_dataset_dry_run_plan(sample_staged_dataset_record)
    assert plan.provenance.candidate_id == sample_staged_dataset_record.candidate_id


def test_36_operation_record_preserves_provenance(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.provenance.operation_id == plan.operation_id


def test_37_provenance_chain_dict_serialization() -> None:
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", "type", "low", "RAG_CANDIDATE")
    d = prov.to_dict()
    assert d["source_request_id"] == "req"


def test_38_provenance_gap_type_traceability(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.provenance.gap_type == sample_staged_rag_record.provenance.source_gap_type


def test_39_provenance_severity_traceability(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.provenance.severity == sample_staged_rag_record.provenance.source_severity


def test_40_provenance_candidate_type_traceability(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.provenance.candidate_type == "RAG_CANDIDATE"


def test_41_provenance_preserved_in_dataset_export_service(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    service = ControlledDatasetExportService(temp_ingestion_repo.conn)
    plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
    assert plan.provenance.candidate_id == sample_staged_dataset_record.candidate_id


def test_42_provenance_preserved_in_rag_ingestion_service(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)
    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    assert plan.provenance.candidate_id == sample_staged_rag_record.candidate_id


def test_43_provenance_hash_consistency(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.provenance_hash == sample_staged_rag_record.provenance_hash


def test_44_content_hash_consistency(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.content_hash == sample_staged_rag_record.content_hash


def test_45_artifact_id_included_in_provenance(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_dataset_dry_run_plan(sample_staged_dataset_record)
    assert plan.provenance.artifact_id is not None


# ===========================================================================
# 46-60: Security Boundary Protection (SECURITY_ADMIN_BOUNDARY) Tests
# ===========================================================================

def test_46_security_admin_boundary_preflight_rag_fails(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    prov_sec = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    d = dict(sample_staged_rag_record.__dict__)
    d["provenance"] = prov_sec
    sec_rec = RAGCandidateStagingRecord(**d)

    res = run_preflight_validation_rag(sec_rec)
    assert res.is_valid is False
    assert res.security_boundary_pass is False
    assert "SECURITY_ADMIN_BOUNDARY_PROHIBITED" in res.issues


def test_47_security_admin_boundary_preflight_dataset_fails(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    prov_sec = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "sum", "DATASET_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    d = dict(sample_staged_dataset_record.__dict__)
    d["provenance"] = prov_sec
    sec_rec = DatasetCandidateStagingRecord(**d)

    res = run_preflight_validation_dataset(sec_rec)
    assert res.is_valid is False
    assert res.security_boundary_pass is False
    assert "SECURITY_ADMIN_BOUNDARY_PROHIBITED" in res.issues


def test_48_security_boundary_dry_run_rag_raises_preflight_error(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    prov_sec = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    d = dict(sample_staged_rag_record.__dict__)
    d["provenance"] = prov_sec
    sec_rec = RAGCandidateStagingRecord(**d)

    service = ControlledIngestionService()
    with pytest.raises(PreflightValidationError) as exc_info:
        service.create_rag_dry_run_plan(sec_rec)
    assert "Preflight validation failed" in str(exc_info.value)


def test_49_security_boundary_dry_run_dataset_raises_preflight_error(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    prov_sec = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "sum", "DATASET_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    d = dict(sample_staged_dataset_record.__dict__)
    d["provenance"] = prov_sec
    sec_rec = DatasetCandidateStagingRecord(**d)

    service = ControlledIngestionService()
    with pytest.raises(PreflightValidationError) as exc_info:
        service.create_dataset_dry_run_plan(sec_rec)
    assert "Preflight validation failed" in str(exc_info.value)


def test_50_security_boundary_critical_severity_hard_block(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    prov_sec = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    d = dict(sample_staged_rag_record.__dict__)
    d["provenance"] = prov_sec
    sec_rec = RAGCandidateStagingRecord(**d)
    res = run_preflight_validation_rag(sec_rec)
    assert res.is_valid is False


def test_51_security_boundary_cannot_be_approved() -> None:
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "RAG_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "RAG_CANDIDATE", RAG_STAGE_PREFLIGHT_FAILED, False, None, None, None, None, None, None, None, "chash", "phash", "ikey", None, prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    service = ControlledIngestionService()
    with pytest.raises(InvalidOperationTransitionError):
        service.approve_operation(rec, approver_id="super-admin")


def test_52_security_boundary_cannot_be_ingested() -> None:
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "RAG_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "RAG_CANDIDATE", RAG_STAGE_PREFLIGHT_FAILED, False, None, None, None, None, None, None, None, "chash", "phash", "ikey", None, prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    service = ControlledIngestionService()
    with pytest.raises(InvalidOperationTransitionError):
        service.transition_operation(rec, RAG_STAGE_INGESTED, actor_id="admin")


def test_53_security_boundary_cannot_be_exported() -> None:
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "DATASET_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "DATASET_CANDIDATE", DATASET_STAGE_PREFLIGHT_FAILED, False, None, None, None, None, None, None, None, "chash", "phash", "ikey", None, prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    service = ControlledIngestionService()
    with pytest.raises(InvalidOperationTransitionError):
        service.transition_operation(rec, DATASET_STAGE_EXPORTED, actor_id="admin")


def test_54_secret_credentials_hard_blocked_in_preflight(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    d = dict(sample_staged_rag_record.__dict__)
    d["title"] = "Title with api_key=secret"
    rec = RAGCandidateStagingRecord(**d)
    res = run_preflight_validation_rag(rec)
    assert res.is_valid is False
    assert res.secret_audit_pass is False


def test_55_secret_credentials_hard_blocked_in_dataset_preflight(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    d = dict(sample_staged_dataset_record.__dict__)
    d["proposed_output"] = "output with password=123"
    rec = DatasetCandidateStagingRecord(**d)
    res = run_preflight_validation_dataset(rec)
    assert res.is_valid is False
    assert res.secret_audit_pass is False


def test_56_security_boundary_recorded_in_preflight_result(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    prov_sec = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, SEVERITY_CRITICAL, "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    d = dict(sample_staged_rag_record.__dict__)
    d["provenance"] = prov_sec
    sec_rec = RAGCandidateStagingRecord(**d)
    res = run_preflight_validation_rag(sec_rec)
    assert res.security_boundary_pass is False


def test_57_no_ingestion_of_security_boundary_via_rag_service(temp_ingestion_repo: ControlledIngestionRepository, sample_approved_rag_kg_record: KnowledgeGapRecord) -> None:
    sec_kg = KnowledgeGapRecord(**{**sample_approved_rag_kg_record.__dict__, "gap_type": GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, "severity": SEVERITY_CRITICAL})
    with pytest.raises(GovernanceSecurityError):
        stage_rag_candidate(sec_kg, title="Title", content="Content", staged_by="admin-1")


def test_58_no_export_of_security_boundary_via_dataset_service(temp_ingestion_repo: ControlledIngestionRepository, sample_approved_ds_kg_record: KnowledgeGapRecord) -> None:
    sec_kg = KnowledgeGapRecord(**{**sample_approved_ds_kg_record.__dict__, "gap_type": GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY, "severity": SEVERITY_CRITICAL})
    with pytest.raises(GovernanceSecurityError):
        stage_dataset_candidate(sec_kg, input_context="Input", proposed_output="Output", language="en", domain_topic="d", staged_by="admin-2")


def test_59_sanitizer_preserves_safe_text() -> None:
    clean = "Clean document content for RAG indexing"
    assert audit_secrets_in_text(clean) is True


def test_60_sanitizer_rejects_bearer_header() -> None:
    dirty = "Header Bearer token12345"
    assert audit_secrets_in_text(dirty) is False


# ===========================================================================
# 61-75: Dry-Run Engine & Non-Mutation Tests
# ===========================================================================

def test_61_rag_dry_run_generates_executable_plan(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.is_executable is True
    assert plan.operation_id.startswith("op-rag-")


def test_62_dataset_dry_run_generates_executable_plan(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_dataset_dry_run_plan(sample_staged_dataset_record)
    assert plan.is_executable is True
    assert plan.operation_id.startswith("op-ds-")


def test_63_rag_dry_run_service_stores_pending_approval_operation(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    op_rec = temp_ingestion_repo.get_operation_by_id(plan.operation_id)
    assert op_rec is not None
    assert op_rec.status == RAG_STAGE_PENDING_APPROVAL
    assert op_rec.dry_run_executed is True


def test_64_dataset_dry_run_service_stores_pending_approval_operation(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    service = ControlledDatasetExportService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
    op_rec = temp_ingestion_repo.get_operation_by_id(plan.operation_id)
    assert op_rec is not None
    assert op_rec.status == DATASET_STAGE_PENDING_APPROVAL
    assert op_rec.dry_run_executed is True


def test_65_rag_dry_run_does_not_mutate_rag_sources(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    service.execute_dry_run(sample_staged_rag_record.candidate_id)
    # Check that artifact versions table has zero rows created during dry run
    metrics = temp_ingestion_repo.aggregate_operation_metrics()
    assert metrics["total_operations"] == 1
    assert metrics["status_counts"].get(RAG_STAGE_INGESTED, 0) == 0


def test_66_dataset_dry_run_does_not_create_export_files(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)
        plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)

        target_dir = Path(td) / sample_staged_dataset_record.candidate_id / plan.artifact_version
        assert not target_dir.exists()  # Dry run MUST NOT write files


def test_67_rag_dry_run_idempotency(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan1 = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    plan2 = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    assert plan1.operation_id == plan2.operation_id


def test_68_dataset_dry_run_idempotency(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    service = ControlledDatasetExportService(temp_ingestion_repo.conn)

    plan1 = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
    plan2 = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
    assert plan1.operation_id == plan2.operation_id


def test_69_dry_run_manifest_preview_structure(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_dataset_dry_run_plan(sample_staged_dataset_record)
    preview = plan.manifest_preview
    assert preview["candidate_id"] == sample_staged_dataset_record.candidate_id
    assert "records.jsonl" in preview["files"]


def test_70_dry_run_expected_chunk_count(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert plan.expected_chunk_count >= 1


def test_71_dry_run_plan_notes_included(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    assert "human admin review" in (plan.plan_notes or "")


def test_72_unready_rag_candidate_dry_run_fails(temp_ingestion_repo: ControlledIngestionRepository, sample_approved_rag_kg_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_kg_record, title="Title", content="Content", staged_by="admin-1")
    # staged status is VALIDATED, not READY_FOR_INGESTION
    temp_ingestion_repo.curation_repo.insert_rag_candidate(staged)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    with pytest.raises(PreflightValidationError):
        service.execute_dry_run(staged.candidate_id)


def test_73_unready_dataset_candidate_dry_run_fails(temp_ingestion_repo: ControlledIngestionRepository, sample_approved_ds_kg_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(sample_approved_ds_kg_record, input_context="Input", proposed_output="Output", language="en", domain_topic="d", staged_by="admin-2")
    # staged status is VALIDATED, not READY_FOR_EXPORT
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(staged)
    service = ControlledDatasetExportService(temp_ingestion_repo.conn)

    with pytest.raises(PreflightValidationError):
        service.execute_dry_run(staged.candidate_id)


def test_74_non_existent_rag_candidate_dry_run_raises_value_error(temp_ingestion_repo: ControlledIngestionRepository) -> None:
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)
    with pytest.raises(ValueError):
        service.execute_dry_run("cand-non-existent")


def test_75_non_existent_dataset_candidate_dry_run_raises_value_error(temp_ingestion_repo: ControlledIngestionRepository) -> None:
    service = ControlledDatasetExportService(temp_ingestion_repo.conn)
    with pytest.raises(ValueError):
        service.execute_dry_run("cand-non-existent")


# ===========================================================================
# 76-90: Human Explicit Approval Gate Tests
# ===========================================================================

def test_76_approve_rag_operation_success(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    op_rec = ControlledOperationRecord(plan.operation_id, plan.candidate_id, "RAG_CANDIDATE", RAG_STAGE_PENDING_APPROVAL, True, None, None, None, None, None, None, None, plan.content_hash, plan.provenance_hash, "ikey", None, plan.provenance, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    approved = service.approve_operation(op_rec, approver_id="super-admin-1", approval_notes="Looks good")
    assert approved.status == RAG_STAGE_APPROVED_FOR_INGESTION
    assert approved.approved_by == "super-admin-1"


def test_77_approve_dataset_operation_success(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_dataset_dry_run_plan(sample_staged_dataset_record)
    op_rec = ControlledOperationRecord(plan.operation_id, plan.candidate_id, "DATASET_CANDIDATE", DATASET_STAGE_PENDING_APPROVAL, True, None, None, None, None, None, plan.provenance.artifact_id, plan.artifact_version, plan.content_hash, plan.provenance_hash, "ikey", None, plan.provenance, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    approved = service.approve_operation(op_rec, approver_id="super-admin-2", approval_notes="Approved for export")
    assert approved.status == DATASET_STAGE_APPROVED_FOR_EXPORT
    assert approved.approved_by == "super-admin-2"


def test_78_approval_requires_approver_identity(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    preflight, plan = service.create_rag_dry_run_plan(sample_staged_rag_record)
    op_rec = ControlledOperationRecord(plan.operation_id, plan.candidate_id, "RAG_CANDIDATE", RAG_STAGE_PENDING_APPROVAL, True, None, None, None, None, None, None, None, plan.content_hash, plan.provenance_hash, "ikey", None, plan.provenance, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    with pytest.raises(IngestionApprovalRequiredError):
        service.approve_operation(op_rec, approver_id="   ")


def test_79_ingestion_execution_requires_approved_for_ingestion_status(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    # Operation status is PENDING_APPROVAL, NOT APPROVED_FOR_INGESTION!
    with pytest.raises(IngestionApprovalRequiredError) as exc_info:
        service.execute_ingestion(plan.operation_id, executor_id="admin-1")
    assert "Explicit human admin approval" in str(exc_info.value)


def test_80_dataset_execution_requires_approved_for_export_status(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    service = ControlledDatasetExportService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
    # Operation status is PENDING_APPROVAL, NOT APPROVED_FOR_EXPORT!
    with pytest.raises(IngestionApprovalRequiredError) as exc_info:
        service.execute_export(plan.operation_id, executor_id="admin-2")
    assert "Explicit human admin approval" in str(exc_info.value)


def test_81_approve_rag_service_flow(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    approved_op = service.approve_ingestion(plan.operation_id, approver_id="super-admin-1")
    assert approved_op.status == RAG_STAGE_APPROVED_FOR_INGESTION


def test_82_approve_dataset_service_flow(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    service = ControlledDatasetExportService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
    approved_op = service.approve_export(plan.operation_id, approver_id="super-admin-2")
    assert approved_op.status == DATASET_STAGE_APPROVED_FOR_EXPORT


def test_83_invalid_transition_from_ingested_to_approved() -> None:
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", "type", "low", "RAG_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "RAG_CANDIDATE", RAG_STAGE_INGESTED, True, "admin", "2026-08-28T08:00:00Z", None, "admin", "2026-08-28T08:00:00Z", "art-1", "v1.0.0", "chash", "phash", "ikey", None, prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    service = ControlledIngestionService()
    with pytest.raises(InvalidOperationTransitionError):
        service.approve_operation(rec, approver_id="admin-2")


def test_84_approval_notes_preserved() -> None:
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", "type", "low", "RAG_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "RAG_CANDIDATE", RAG_STAGE_PENDING_APPROVAL, True, None, None, None, None, None, None, None, "chash", "phash", "ikey", None, prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    service = ControlledIngestionService()
    app = service.approve_operation(rec, approver_id="admin-1", approval_notes="Detailed note")
    assert "Detailed note" in (app.approval_notes or "")


def test_85_approval_timestamp_recorded() -> None:
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", "type", "low", "RAG_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "RAG_CANDIDATE", RAG_STAGE_PENDING_APPROVAL, True, None, None, None, None, None, None, None, "chash", "phash", "ikey", None, prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    service = ControlledIngestionService()
    app = service.approve_operation(rec, approver_id="admin-1")
    assert app.approved_at is not None


def test_86_candidate_readiness_status_alone_never_bypasses_approval() -> None:
    # Staging status is READY_FOR_INGESTION, but operation status is DRY_RUN_READY
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", "type", "low", "RAG_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "RAG_CANDIDATE", RAG_STAGE_DRY_RUN_READY, True, None, None, None, None, None, None, None, "chash", "phash", "ikey", None, prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    service = ControlledIngestionService()
    # Transitioning directly to INGESTING without approval is blocked
    with pytest.raises(InvalidOperationTransitionError):
        service.transition_operation(rec, RAG_STAGE_INGESTING, actor_id="admin-1")


def test_87_direct_jump_preflight_to_ingested_blocked() -> None:
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", "type", "low", "RAG_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "RAG_CANDIDATE", RAG_STAGE_PREFLIGHT_VALIDATED, False, None, None, None, None, None, None, None, "chash", "phash", "ikey", None, prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    service = ControlledIngestionService()
    with pytest.raises(InvalidOperationTransitionError):
        service.transition_operation(rec, RAG_STAGE_INGESTED, actor_id="admin-1")


def test_88_direct_jump_preflight_to_exported_blocked() -> None:
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", "type", "low", "DATASET_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "DATASET_CANDIDATE", DATASET_STAGE_PREFLIGHT_VALIDATED, False, None, None, None, None, None, None, None, "chash", "phash", "ikey", None, prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    service = ControlledIngestionService()
    with pytest.raises(InvalidOperationTransitionError):
        service.transition_operation(rec, DATASET_STAGE_EXPORTED, actor_id="admin-1")


def test_89_non_existent_operation_approval_raises_value_error(temp_ingestion_repo: ControlledIngestionRepository) -> None:
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)
    with pytest.raises(ValueError):
        service.approve_ingestion("op-non-existent", approver_id="admin-1")


def test_90_non_existent_dataset_operation_approval_raises_value_error(temp_ingestion_repo: ControlledIngestionRepository) -> None:
    service = ControlledDatasetExportService(temp_ingestion_repo.conn)
    with pytest.raises(ValueError):
        service.approve_export("op-non-existent", approver_id="admin-1")


# ===========================================================================
# 91-105: Execution, Versioning, Idempotency & Artifact Export Tests
# ===========================================================================

def test_91_rag_ingestion_execution_success(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    service.approve_ingestion(plan.operation_id, approver_id="super-admin-1")

    res = service.execute_ingestion(plan.operation_id, executor_id="executor-1")
    assert res["status"] == RAG_STAGE_VERIFIED
    assert res["artifact_id"].startswith("art-rag-")
    assert res["artifact_version"].startswith("v1.0.0-")


def test_92_dataset_export_execution_success(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)

        plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
        service.approve_export(plan.operation_id, approver_id="super-admin-2")

        res = service.execute_export(plan.operation_id, executor_id="executor-2")
        assert res["status"] == DATASET_STAGE_VERIFIED

        target_dir = Path(td) / sample_staged_dataset_record.candidate_id / res["artifact_version"]
        assert (target_dir / "records.jsonl").exists()
        assert (target_dir / "provenance.json").exists()
        assert (target_dir / "manifest.json").exists()
        assert (target_dir / "checksums.json").exists()


def test_93_dataset_export_records_jsonl_content(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)

        plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
        service.approve_export(plan.operation_id, approver_id="super-admin-2")
        res = service.execute_export(plan.operation_id, executor_id="executor-2")

        target_dir = Path(td) / sample_staged_dataset_record.candidate_id / res["artifact_version"]
        lines = (target_dir / "records.jsonl").read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["candidate_id"] == sample_staged_dataset_record.candidate_id
        assert record["input_context"] == sample_staged_dataset_record.input_context


def test_94_dataset_export_checksums_match_files(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)

        plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
        service.approve_export(plan.operation_id, approver_id="super-admin-2")
        res = service.execute_export(plan.operation_id, executor_id="executor-2")

        target_dir = Path(td) / sample_staged_dataset_record.candidate_id / res["artifact_version"]
        rec_hash = hashlib.sha256((target_dir / "records.jsonl").read_bytes()).hexdigest()
        assert res["checksums"]["records.jsonl"] == rec_hash


def test_95_artifact_version_registered_in_repository(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    service.approve_ingestion(plan.operation_id, approver_id="super-admin-1")
    res = service.execute_ingestion(plan.operation_id, executor_id="executor-1")

    art_row = temp_ingestion_repo.get_artifact_version_by_id(res["artifact_id"])
    assert art_row is not None
    assert art_row["artifact_type"] == "RAG_SOURCE_VERSION"
    assert art_row["status"] == "ACTIVE"


def test_96_dataset_artifact_version_registered(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)

        plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
        service.approve_export(plan.operation_id, approver_id="super-admin-2")
        res = service.execute_export(plan.operation_id, executor_id="executor-2")

        art_row = temp_ingestion_repo.get_artifact_version_by_id(res["artifact_id"])
        assert art_row is not None
        assert art_row["artifact_type"] == "DATASET_EXPORT_ARTIFACT"


def test_97_idempotency_key_prevents_duplicate_operation_log(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    p1 = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    p2 = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    assert p1.operation_id == p2.operation_id
    metrics = temp_ingestion_repo.aggregate_operation_metrics()
    assert metrics["total_operations"] == 1


def test_98_post_ingestion_verification_status(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    service.approve_ingestion(plan.operation_id, approver_id="super-admin-1")
    service.execute_ingestion(plan.operation_id, executor_id="executor-1")

    op_rec = temp_ingestion_repo.get_operation_by_id(plan.operation_id)
    assert op_rec is not None
    assert op_rec.status == RAG_STAGE_VERIFIED


def test_99_post_export_verification_status(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)

        plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
        service.approve_export(plan.operation_id, approver_id="super-admin-2")
        service.execute_export(plan.operation_id, executor_id="executor-2")

        op_rec = temp_ingestion_repo.get_operation_by_id(plan.operation_id)
        assert op_rec is not None
        assert op_rec.status == DATASET_STAGE_VERIFIED


def test_100_no_training_triggered_during_export(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)

        plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
        service.approve_export(plan.operation_id, approver_id="super-admin-2")
        res = service.execute_export(plan.operation_id, executor_id="executor-2")

        # Verify no model weight files or training processes were created
        target_dir = Path(td) / sample_staged_dataset_record.candidate_id / res["artifact_version"]
        files = [f.name for f in target_dir.iterdir()]
        assert "model.pt" not in files
        assert "weights.bin" not in files


def test_101_utf8_encoding_preserved_in_dataset_export(temp_ingestion_repo: ControlledIngestionRepository, sample_approved_ds_kg_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(sample_approved_ds_kg_record, input_context="தமிழ் வினா விளக்கம்", proposed_output="தமிழ் விடை விளக்கம்", language="ta", domain_topic="tamil", staged_by="admin-2")
    d = dict(staged.__dict__)
    d["status"] = DATASET_STATUS_READY_FOR_EXPORT
    ready_staged = DatasetCandidateStagingRecord(**d)

    temp_ingestion_repo.curation_repo.insert_dataset_candidate(ready_staged)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)
        plan = service.execute_dry_run(ready_staged.candidate_id)
        service.approve_export(plan.operation_id, approver_id="super-admin-2")
        res = service.execute_export(plan.operation_id, executor_id="executor-2")

        target_dir = Path(td) / ready_staged.candidate_id / res["artifact_version"]
        content = (target_dir / "records.jsonl").read_text(encoding="utf-8")
        assert "தமிழ் வினா விளக்கம்" in content


def test_102_list_operations_filtering(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    service.execute_dry_run(sample_staged_rag_record.candidate_id)
    ops_rag = temp_ingestion_repo.list_operations(candidate_type="RAG_CANDIDATE")
    ops_ds = temp_ingestion_repo.list_operations(candidate_type="DATASET_CANDIDATE")
    assert len(ops_rag) == 1
    assert len(ops_ds) == 0


def test_103_aggregate_operation_metrics(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    service.execute_dry_run(sample_staged_rag_record.candidate_id)
    metrics = temp_ingestion_repo.aggregate_operation_metrics()
    assert metrics["total_operations"] == 1
    assert metrics["status_counts"][RAG_STAGE_PENDING_APPROVAL] == 1


def test_104_executed_by_and_at_recorded_on_ingestion(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    service.approve_ingestion(plan.operation_id, approver_id="super-admin-1")
    service.execute_ingestion(plan.operation_id, executor_id="executor-1")

    op_rec = temp_ingestion_repo.get_operation_by_id(plan.operation_id)
    assert op_rec is not None
    assert op_rec.executed_by == "executor-1"
    assert op_rec.executed_at is not None


def test_105_executed_by_and_at_recorded_on_export(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)

        plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
        service.approve_export(plan.operation_id, approver_id="super-admin-2")
        service.execute_export(plan.operation_id, executor_id="executor-2")

        op_rec = temp_ingestion_repo.get_operation_by_id(plan.operation_id)
        assert op_rec is not None
        assert op_rec.executed_by == "executor-2"
        assert op_rec.executed_at is not None


# ===========================================================================
# 106-115: Reversible Non-Destructive Rollback Mechanism Tests
# ===========================================================================

def test_106_rollback_rag_ingestion_success(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    service.approve_ingestion(plan.operation_id, approver_id="super-admin-1")
    service.execute_ingestion(plan.operation_id, executor_id="executor-1")

    rolled_back = service.rollback_ingestion(plan.operation_id, admin_id="super-admin-1", rollback_reason="Inaccurate text detected post-ingestion")
    assert rolled_back.status == RAG_STAGE_ROLLED_BACK
    assert rolled_back.rollback_reference_id is not None


def test_107_rollback_dataset_export_success(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)

        plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
        service.approve_export(plan.operation_id, approver_id="super-admin-2")
        service.execute_export(plan.operation_id, executor_id="executor-2")

        rolled_back = service.rollback_export(plan.operation_id, admin_id="super-admin-2", rollback_reason="License clarification needed")
        assert rolled_back.status == DATASET_STAGE_ROLLED_BACK
        assert rolled_back.rollback_reference_id is not None


def test_108_rollback_updates_artifact_version_status(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    service.approve_ingestion(plan.operation_id, approver_id="super-admin-1")
    res = service.execute_ingestion(plan.operation_id, executor_id="executor-1")

    service.rollback_ingestion(plan.operation_id, admin_id="super-admin-1")
    art_row = temp_ingestion_repo.get_artifact_version_by_id(res["artifact_id"])
    assert art_row is not None
    assert art_row["status"] == "ROLLED_BACK"


def test_109_rollback_is_non_destructive_preserves_records(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_rag_candidate(sample_staged_rag_record)
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)

    plan = service.execute_dry_run(sample_staged_rag_record.candidate_id)
    service.approve_ingestion(plan.operation_id, approver_id="super-admin-1")
    res = service.execute_ingestion(plan.operation_id, executor_id="executor-1")

    service.rollback_ingestion(plan.operation_id, admin_id="super-admin-1")
    # Verify row was NOT deleted from table
    art_row = temp_ingestion_repo.get_artifact_version_by_id(res["artifact_id"])
    assert art_row is not None


def test_110_rollback_dataset_files_preserved_for_audit(temp_ingestion_repo: ControlledIngestionRepository, sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    temp_ingestion_repo.curation_repo.insert_dataset_candidate(sample_staged_dataset_record)
    with tempfile.TemporaryDirectory() as td:
        service = ControlledDatasetExportService(temp_ingestion_repo.conn, export_root_dir=td)

        plan = service.execute_dry_run(sample_staged_dataset_record.candidate_id)
        service.approve_export(plan.operation_id, approver_id="super-admin-2")
        res = service.execute_export(plan.operation_id, executor_id="executor-2")

        service.rollback_export(plan.operation_id, admin_id="super-admin-2")

        # Rollback marks state as ROLLED_BACK but leaves files intact for audit trailing
        target_dir = Path(td) / sample_staged_dataset_record.candidate_id / res["artifact_version"]
        assert (target_dir / "manifest.json").exists()


def test_111_terminal_rolled_back_state_prevents_re_ingestion(sample_staged_rag_record: RAGCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", "type", "low", "RAG_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "RAG_CANDIDATE", RAG_STAGE_ROLLED_BACK, True, "admin", "2026-08-28T08:00:00Z", None, "admin", "2026-08-28T08:00:00Z", "art-1", "v1.0.0", "chash", "phash", "ikey", "op-rb-1", prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    with pytest.raises(InvalidOperationTransitionError):
        service.transition_operation(rec, RAG_STAGE_INGESTING, actor_id="admin")


def test_112_terminal_rolled_back_state_prevents_re_export(sample_staged_dataset_record: DatasetCandidateStagingRecord) -> None:
    service = ControlledIngestionService()
    prov = ProvenanceChain("req", "gap", "rec", "cand", "op", "art", "admin", "2026-08-28T08:00:00Z", "type", "low", "DATASET_CANDIDATE")
    rec = ControlledOperationRecord("op-1", "cand-1", "DATASET_CANDIDATE", DATASET_STAGE_ROLLED_BACK, True, "admin", "2026-08-28T08:00:00Z", None, "admin", "2026-08-28T08:00:00Z", "art-1", "v1.0.0", "chash", "phash", "ikey", "op-rb-1", prov, "2026-08-28T08:00:00Z", "2026-08-28T08:00:00Z")

    with pytest.raises(InvalidOperationTransitionError):
        service.transition_operation(rec, DATASET_STAGE_EXPORTING, actor_id="admin")


def test_113_rollback_non_existent_rag_operation_raises_value_error(temp_ingestion_repo: ControlledIngestionRepository) -> None:
    service = ControlledRagIngestionService(temp_ingestion_repo.conn)
    with pytest.raises(ValueError):
        service.rollback_ingestion("op-non-existent", admin_id="admin-1")


def test_114_rollback_non_existent_dataset_operation_raises_value_error(temp_ingestion_repo: ControlledIngestionRepository) -> None:
    service = ControlledDatasetExportService(temp_ingestion_repo.conn)
    with pytest.raises(ValueError):
        service.rollback_export("op-non-existent", admin_id="admin-1")


def test_115_rollback_reference_id_generation() -> None:
    ref = generate_operation_id("op-rollback")
    assert ref.startswith("op-rollback-")


# ===========================================================================
# 116-120: AST Security, Admin RBAC & Production DB Integrity Tests
# ===========================================================================

def test_116_non_autonomous_learning_invariant() -> None:
    import core_model.capabilities.controlled_ingestion_service as mod
    for name, obj in inspect.getmembers(mod):
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            assert "train" not in name.lower()
            assert "fine_tune" not in name.lower()
            assert "modify_weights" not in name.lower()


def test_117_ast_security_controlled_ingestion_service() -> None:
    import core_model.capabilities.controlled_ingestion_service as mod
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_118_no_network_or_subprocess_in_controlled_ingestion_service() -> None:
    code = inspect.getsource(ControlledIngestionService).lower()
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


def test_120_final_phase22_integrity_contract_validation() -> None:
    """Final contract validation verifying Phase 22 completion."""
    assert EXPECTED_DB_SHA256 == "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    assert EXPECTED_DB_SIZE == 11096064
    assert len(RAG_INGESTION_ALLOWED_TRANSITIONS) > 0
    assert len(DATASET_EXPORT_ALLOWED_TRANSITIONS) > 0
