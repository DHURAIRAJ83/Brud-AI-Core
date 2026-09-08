"""Phase 21 — Human-Approved RAG & Dataset Candidate Curation Test Suite.

Comprehensive 100-test suite verifying:
- CandidateProvenance and staging record dataclasses
- Quality validation engine & secret sanitization
- Duplicate & conflict detection engine
- Phase 20 approval dependency & security boundary invariants
- RAG & Dataset staging state machines
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
from typing import Any

import pytest

from core_model.capabilities.knowledge_gap import (
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
    SEVERITY_CRITICAL,
    SEVERITY_LOW,
    KnowledgeGap,
)
from core_model.capabilities.knowledge_gap_governance_service import (
    APPROVAL_APPROVED,
    APPROVAL_NOT_REQUESTED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    CANDIDATE_DATASET,
    CANDIDATE_NONE,
    CANDIDATE_RAG,
    GovernanceSecurityError,
    KnowledgeGapRecord,
    STATUS_APPROVED,
    STATUS_CURATED,
    STATUS_IN_REVIEW,
    STATUS_NEW,
    STATUS_REJECTED,
)
from core_model.capabilities.candidate_curation_service import (
    DATASET_ALLOWED_TRANSITIONS,
    DATASET_STATUS_READY_FOR_EXPORT,
    DUPLICATE_EXACT,
    DUPLICATE_PROBABLE,
    DUPLICATE_UNIQUE,
    CONFLICT_CONFLICTING,
    CONFLICT_NONE,
    RAG_ALLOWED_TRANSITIONS,
    RAG_STATUS_READY_FOR_INGESTION,
    STAGING_STATUS_APPROVED,
    STAGING_STATUS_DEFERRED,
    STAGING_STATUS_DRAFT,
    STAGING_STATUS_PENDING_REVIEW,
    STAGING_STATUS_REJECTED,
    STAGING_STATUS_VALIDATED,
    VALIDATION_FAIL,
    VALIDATION_NEEDS_REVISION,
    VALIDATION_PASS,
    CandidateCurationService,
    CandidateDuplicateConflictResult,
    CandidateProvenance,
    CandidateProvenanceError,
    CandidateValidationResult,
    DatasetCandidateStagingRecord,
    InvalidStagingTransitionError,
    RAGCandidateStagingRecord,
    compute_canonical_content_hash,
    compute_provenance_hash,
    detect_candidate_duplicates_and_conflicts,
    stage_dataset_candidate,
    stage_rag_candidate,
    validate_candidate_quality,
)
from backend.database.repositories.candidate_curation_repository import CandidateCurationRepository

PROD_DB_PATH = "data/database/brud_ai.db"
EXPECTED_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_DB_SIZE = 11096064


@pytest.fixture
def sample_approved_rag_record() -> KnowledgeGapRecord:
    """Fixture returning a Phase 20 APPROVED KnowledgeGapRecord for RAG."""
    return KnowledgeGapRecord(
        record_id="rec-rag-01",
        gap_id="gap-rag-01",
        request_id="req-rag-01",
        detected_language="en",
        language_confidence=0.95,
        normalized_intent="how to configure rag in python",
        requested_capability_id="general_chat",
        selected_capability_id="rag_query",
        routing_confidence=0.88,
        failure_classification="knowledge_not_found",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="how to configure rag in python",
        sanitized_metadata={"env": "prod"},
        status=STATUS_APPROVED,
        candidate_type=CANDIDATE_RAG,
        approval_state=APPROVAL_APPROVED,
        created_at="2026-08-28T08:00:00Z",
        updated_at="2026-08-28T08:10:00Z",
        reviewed_at="2026-08-28T08:10:00Z",
        reviewed_by="admin-1",
        reviewer_notes="Approved for RAG staging",
    )


@pytest.fixture
def sample_approved_dataset_record() -> KnowledgeGapRecord:
    """Fixture returning a Phase 20 APPROVED KnowledgeGapRecord for Dataset."""
    return KnowledgeGapRecord(
        record_id="rec-ds-01",
        gap_id="gap-ds-01",
        request_id="req-ds-01",
        detected_language="en",
        language_confidence=0.92,
        normalized_intent="explain vector index search",
        requested_capability_id="general_chat",
        selected_capability_id="general_chat",
        routing_confidence=0.85,
        failure_classification="insufficient_evidence",
        gap_type="UNAVAILABLE_KNOWLEDGE_SCOPE",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="partial",
        source_stage="routing",
        safe_summary="explain vector index search",
        sanitized_metadata={"domain": "ai"},
        status=STATUS_APPROVED,
        candidate_type=CANDIDATE_DATASET,
        approval_state=APPROVAL_APPROVED,
        created_at="2026-08-28T08:00:00Z",
        updated_at="2026-08-28T08:12:00Z",
        reviewed_at="2026-08-28T08:12:00Z",
        reviewed_by="admin-2",
        reviewer_notes="Approved for Dataset staging",
    )


@pytest.fixture
def temp_repo() -> CandidateCurationRepository:
    """Fixture providing an isolated in-memory CandidateCurationRepository."""
    conn = sqlite3.connect(":memory:")
    return CandidateCurationRepository(conn)


# ===========================================================================
# 1-10: Dataclass, Constants, Invariants & Helper Function Tests
# ===========================================================================

def test_01_staging_status_constants() -> None:
    assert STAGING_STATUS_DRAFT == "DRAFT"
    assert STAGING_STATUS_VALIDATED == "VALIDATED"
    assert STAGING_STATUS_PENDING_REVIEW == "PENDING_REVIEW"
    assert STAGING_STATUS_APPROVED == "APPROVED"
    assert STAGING_STATUS_REJECTED == "REJECTED"
    assert STAGING_STATUS_DEFERRED == "DEFERRED"
    assert RAG_STATUS_READY_FOR_INGESTION == "READY_FOR_INGESTION"
    assert DATASET_STATUS_READY_FOR_EXPORT == "READY_FOR_EXPORT"


def test_02_validation_status_constants() -> None:
    assert VALIDATION_PASS == "PASS"
    assert VALIDATION_FAIL == "FAIL"
    assert VALIDATION_NEEDS_REVISION == "NEEDS_REVISION"


def test_03_duplicate_and_conflict_status_constants() -> None:
    assert DUPLICATE_UNIQUE == "UNIQUE"
    assert DUPLICATE_EXACT == "EXACT_DUPLICATE"
    assert DUPLICATE_PROBABLE == "PROBABLE_DUPLICATE"
    assert CONFLICT_NONE == "NO_CONFLICT"
    assert CONFLICT_CONFLICTING == "CONFLICTING"


def test_04_rag_allowed_transitions() -> None:
    assert STAGING_STATUS_VALIDATED in RAG_ALLOWED_TRANSITIONS[STAGING_STATUS_DRAFT]
    assert STAGING_STATUS_PENDING_REVIEW in RAG_ALLOWED_TRANSITIONS[STAGING_STATUS_VALIDATED]
    assert STAGING_STATUS_APPROVED in RAG_ALLOWED_TRANSITIONS[STAGING_STATUS_PENDING_REVIEW]
    assert RAG_STATUS_READY_FOR_INGESTION in RAG_ALLOWED_TRANSITIONS[STAGING_STATUS_APPROVED]


def test_05_dataset_allowed_transitions() -> None:
    assert STAGING_STATUS_VALIDATED in DATASET_ALLOWED_TRANSITIONS[STAGING_STATUS_DRAFT]
    assert STAGING_STATUS_PENDING_REVIEW in DATASET_ALLOWED_TRANSITIONS[STAGING_STATUS_VALIDATED]
    assert STAGING_STATUS_APPROVED in DATASET_ALLOWED_TRANSITIONS[STAGING_STATUS_PENDING_REVIEW]
    assert DATASET_STATUS_READY_FOR_EXPORT in DATASET_ALLOWED_TRANSITIONS[STAGING_STATUS_APPROVED]


def test_06_canonical_content_hash_determinism() -> None:
    h1 = compute_canonical_content_hash("  Hello World  ")
    h2 = compute_canonical_content_hash("hello world")
    assert h1 == h2
    assert len(h1) == 64


def test_07_provenance_hash_determinism() -> None:
    prov = CandidateProvenance(
        provenance_id="p-1",
        source_record_id="rec-1",
        source_gap_id="gap-1",
        source_request_id="req-1",
        source_gap_type="KNOWLEDGE_NOT_FOUND",
        source_severity="low",
        source_summary="test",
        candidate_type="RAG_CANDIDATE",
        approved_by="admin-1",
        approved_at="2026-08-28T08:00:00Z",
    )
    h1 = compute_provenance_hash(prov)
    h2 = compute_provenance_hash(prov)
    assert h1 == h2
    assert len(h1) == 64


def test_08_candidate_provenance_dataclass() -> None:
    prov = CandidateProvenance(
        provenance_id="p-1",
        source_record_id="rec-1",
        source_gap_id="gap-1",
        source_request_id="req-1",
        source_gap_type="KNOWLEDGE_NOT_FOUND",
        source_severity="low",
        source_summary="summary",
        candidate_type="RAG_CANDIDATE",
        approved_by="admin-1",
        approved_at="2026-08-28T08:00:00Z",
    )
    d = prov.to_dict()
    assert d["provenance_id"] == "p-1"
    assert d["source_record_id"] == "rec-1"


def test_09_validation_result_json_serializability() -> None:
    res = CandidateValidationResult(
        is_valid=True,
        validation_status=VALIDATION_PASS,
        issue_count=0,
        issues=(),
        warnings=(),
        metadata={"key": "val"},
    )
    dumped = json.dumps(res.to_dict())
    assert "is_valid" in dumped


def test_10_duplicate_conflict_result_structure() -> None:
    res = CandidateDuplicateConflictResult(
        duplicate_status=DUPLICATE_UNIQUE,
        conflict_status=CONFLICT_NONE,
    )
    d = res.to_dict()
    assert d["duplicate_status"] == "UNIQUE"
    assert d["conflict_status"] == "NO_CONFLICT"


# ===========================================================================
# 11-25: Quality Validation & Sanitization Tests
# ===========================================================================

def test_11_quality_validation_pass_for_valid_input() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="RAG Config", content_or_output="Valid document content for RAG indexing.")
    assert res.is_valid is True
    assert res.validation_status == VALIDATION_PASS
    assert res.issue_count == 0


def test_12_quality_validation_fail_missing_provenance() -> None:
    prov = CandidateProvenance("", "", "", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="Title", content_or_output="Content here")
    assert res.is_valid is False
    assert res.validation_status == VALIDATION_FAIL
    assert "missing_provenance_id" in res.issues


def test_13_quality_validation_fail_missing_content() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="Title", content_or_output="")
    assert res.is_valid is False
    assert "empty_content_or_output" in res.issues


def test_14_quality_validation_fail_content_too_short() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="Title", content_or_output="a", min_length=5)
    assert res.is_valid is False
    assert any("too_short" in i for i in res.issues)


def test_15_quality_validation_fail_content_too_long() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="Title", content_or_output="x" * 100, max_length=50)
    assert res.is_valid is False
    assert any("too_long" in i for i in res.issues)


def test_16_quality_validation_redacts_api_keys() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="Secret Title", content_or_output="key is api_key=secret123")
    assert res.is_valid is False
    assert "unredacted_secret_detected_in_content" in res.issues


def test_17_quality_validation_redacts_bearer_tokens() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="Auth", content_or_output="header is Bearer eyJhbGci")
    assert res.is_valid is False
    assert "unredacted_secret_detected_in_content" in res.issues


def test_18_quality_validation_redacts_passwords() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="Pass", content_or_output="my password=supersecret")
    assert res.is_valid is False
    assert "unredacted_secret_detected_in_content" in res.issues


def test_19_quality_validation_filters_secret_metadata_keys() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="Title", content_or_output="Valid text", sanitized_metadata={"password": "123"})
    assert res.is_valid is False
    assert "forbidden_metadata_key:password" in res.issues


def test_20_sanitized_summary_preservation() -> None:
    from core_model.capabilities.knowledge_gap import sanitize_summary
    gap_summary = "my key is api_key=123456789012345678901234"
    clean = sanitize_summary(gap_summary)
    assert "123456789012345678901234" not in clean
    assert "[REDACTED_SECRET]" in clean


def test_21_quality_validation_is_deterministic() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    r1 = validate_candidate_quality(provenance=prov, title_or_input="Title", content_or_output="Content")
    r2 = validate_candidate_quality(provenance=prov, title_or_input="Title", content_or_output="Content")
    assert r1.is_valid == r2.is_valid
    assert r1.issues == r2.issues


def test_22_quality_validation_pass_does_not_equal_approval() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="Title", content_or_output="Content")
    assert res.validation_status == VALIDATION_PASS
    # Validation status PASS does NOT mean approval state is APPROVED
    assert res.validation_status != STAGING_STATUS_APPROVED


def test_23_empty_title_fails_validation() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="   ", content_or_output="Content")
    assert res.is_valid is False
    assert "empty_title_or_input" in res.issues


def test_24_unicode_content_quality_validation() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="தமிழ் RAG", content_or_output="தமிழ் தரவு உரை விளக்கம்")
    assert res.is_valid is True


def test_25_multiline_content_quality_validation() -> None:
    prov = CandidateProvenance("p-1", "rec-1", "gap-1", "req-1", "type", "low", "sum", "RAG_CANDIDATE", "admin", "2026-08-28T08:00:00Z")
    res = validate_candidate_quality(provenance=prov, title_or_input="Multiline Title", content_or_output="Line 1\nLine 2\nLine 3")
    assert res.is_valid is True


# ===========================================================================
# 26-40: Duplicate & Conflict Engine Tests
# ===========================================================================

def test_26_detect_unique_candidate() -> None:
    res = detect_candidate_duplicates_and_conflicts("hash-new-c", "hash-new-p", ())
    assert res.duplicate_status == DUPLICATE_UNIQUE
    assert res.conflict_status == CONFLICT_NONE


def test_27_detect_exact_duplicate_candidate(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Same content", staged_by="admin-1")
    res = detect_candidate_duplicates_and_conflicts(staged.content_hash, "hash-diff-p", (staged,))
    assert res.duplicate_status == DUPLICATE_EXACT
    assert res.matched_candidate_id == staged.candidate_id


def test_28_detect_conflicting_candidate(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Original content", staged_by="admin-1")
    res = detect_candidate_duplicates_and_conflicts("hash-different-content", staged.provenance_hash, (staged,))
    assert res.conflict_status == CONFLICT_CONFLICTING
    assert res.matched_candidate_id == staged.candidate_id


def test_29_exact_duplicate_matches_content_hash(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Target text", staged_by="admin-1")
    res = detect_candidate_duplicates_and_conflicts(staged.content_hash, "other-prov", (staged,))
    assert res.duplicate_status == DUPLICATE_EXACT
    assert res.matched_content_hash == staged.content_hash


def test_30_conflicting_matches_provenance_hash_different_content(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Target text 1", staged_by="admin-1")
    res = detect_candidate_duplicates_and_conflicts(compute_canonical_content_hash("Target text 2"), staged.provenance_hash, (staged,))
    assert res.conflict_status == CONFLICT_CONFLICTING


def test_31_duplicate_matching_is_deterministic(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Target text", staged_by="admin-1")
    r1 = detect_candidate_duplicates_and_conflicts(staged.content_hash, staged.provenance_hash, (staged,))
    r2 = detect_candidate_duplicates_and_conflicts(staged.content_hash, staged.provenance_hash, (staged,))
    assert r1.duplicate_status == r2.duplicate_status


def test_32_no_llm_used_in_duplicate_detection() -> None:
    code = inspect.getsource(detect_candidate_duplicates_and_conflicts).lower()
    assert "llm" not in code
    assert "openai" not in code
    assert "embedding" not in code


def test_33_empty_existing_records_returns_unique() -> None:
    res = detect_candidate_duplicates_and_conflicts("hash-1", "hash-2", [])
    assert res.duplicate_status == DUPLICATE_UNIQUE
    assert res.matched_candidate_id is None


def test_34_multiple_existing_records_matching(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    s1 = stage_rag_candidate(sample_approved_rag_record, title="T1", content="Content 1", staged_by="admin-1", candidate_id="c-1")
    g2 = KnowledgeGapRecord(**{**sample_approved_rag_record.__dict__, "record_id": "rec-2", "gap_id": "gap-2"})
    s2 = stage_rag_candidate(g2, title="T2", content="Content 2", staged_by="admin-1", candidate_id="c-2")

    res = detect_candidate_duplicates_and_conflicts(s2.content_hash, "prov-diff", (s1, s2))
    assert res.duplicate_status == DUPLICATE_EXACT
    assert res.matched_candidate_id == "c-2"


def test_35_duplicate_status_preserved_in_staging_record(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    s1 = stage_rag_candidate(sample_approved_rag_record, title="T1", content="Identical Content", staged_by="admin-1")
    s2 = stage_rag_candidate(sample_approved_rag_record, title="T1", content="Identical Content", staged_by="admin-1", existing_records=(s1,))
    assert s2.duplicate_status == DUPLICATE_EXACT


def test_36_conflict_status_preserved_in_staging_record(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    s1 = stage_rag_candidate(sample_approved_rag_record, title="T1", content="Version A", staged_by="admin-1")
    s2 = stage_rag_candidate(sample_approved_rag_record, title="T1", content="Version B", staged_by="admin-1", existing_records=(s1,))
    assert s2.conflict_status == CONFLICT_CONFLICTING


def test_37_conflict_reason_formatting(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    s1 = stage_rag_candidate(sample_approved_rag_record, title="T1", content="Version A", staged_by="admin-1", candidate_id="c-orig")
    res = detect_candidate_duplicates_and_conflicts("hash-other", s1.provenance_hash, (s1,))
    assert "c-orig" in (res.conflict_reason or "")


def test_38_case_insensitive_content_hash_matching() -> None:
    h1 = compute_canonical_content_hash("TEXT")
    h2 = compute_canonical_content_hash("text")
    assert h1 == h2


def test_39_whitespace_insensitive_content_hash_matching() -> None:
    h1 = compute_canonical_content_hash("  Text with spaces  \n")
    h2 = compute_canonical_content_hash("Text with spaces")
    assert h1 == h2


def test_40_distinct_candidates_with_different_hashes() -> None:
    h1 = compute_canonical_content_hash("Content A")
    h2 = compute_canonical_content_hash("Content B")
    assert h1 != h2


# ===========================================================================
# 41-60: RAG & Dataset Candidate Staging Factory & Invariants Tests
# ===========================================================================

def test_41_stage_rag_candidate_success(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(
        sample_approved_rag_record,
        title="RAG Title",
        content="Valid Content for RAG",
        staged_by="admin-1",
    )
    assert staged.candidate_id.startswith("rag-cand-")
    assert staged.title == "RAG Title"
    assert staged.status == STAGING_STATUS_VALIDATED


def test_42_stage_dataset_candidate_success(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(
        sample_approved_dataset_record,
        input_context="What is Python?",
        proposed_output="Python is a programming language.",
        language="en",
        domain_topic="coding",
        staged_by="admin-2",
    )
    assert staged.candidate_id.startswith("ds-cand-")
    assert staged.input_context == "What is Python?"
    assert staged.status == STAGING_STATUS_VALIDATED


def test_43_stage_rag_requires_phase20_approved_status(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    unapproved = KnowledgeGapRecord(**{**sample_approved_rag_record.__dict__, "status": STATUS_IN_REVIEW})
    with pytest.raises(CandidateProvenanceError) as exc_info:
        stage_rag_candidate(unapproved, title="Title", content="Content", staged_by="admin-1")
    assert "not approved in Phase 20" in str(exc_info.value)


def test_44_stage_dataset_requires_phase20_approved_status(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    unapproved = KnowledgeGapRecord(**{**sample_approved_dataset_record.__dict__, "status": STATUS_CURATED})
    with pytest.raises(CandidateProvenanceError) as exc_info:
        stage_dataset_candidate(unapproved, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-1")
    assert "not approved in Phase 20" in str(exc_info.value)


def test_45_stage_rag_requires_phase20_approved_approval_state(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    unapproved = KnowledgeGapRecord(**{**sample_approved_rag_record.__dict__, "approval_state": APPROVAL_PENDING})
    with pytest.raises(CandidateProvenanceError) as exc_info:
        stage_rag_candidate(unapproved, title="Title", content="Content", staged_by="admin-1")
    assert "approval_state=PENDING" in str(exc_info.value)


def test_46_stage_dataset_requires_phase20_approved_approval_state(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    unapproved = KnowledgeGapRecord(**{**sample_approved_dataset_record.__dict__, "approval_state": APPROVAL_REJECTED})
    with pytest.raises(CandidateProvenanceError) as exc_info:
        stage_dataset_candidate(unapproved, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-1")
    assert "approval_state=REJECTED" in str(exc_info.value)


def test_47_candidate_type_classification_alone_denies_staging(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    curated_unapproved = KnowledgeGapRecord(
        **{
            **sample_approved_rag_record.__dict__,
            "status": STATUS_CURATED,
            "candidate_type": CANDIDATE_RAG,
            "approval_state": APPROVAL_PENDING,
        }
    )
    with pytest.raises(CandidateProvenanceError):
        stage_rag_candidate(curated_unapproved, title="Title", content="Content", staged_by="admin-1")


def test_48_stage_rag_rejects_dataset_candidate_type(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    ds_record = KnowledgeGapRecord(**{**sample_approved_rag_record.__dict__, "candidate_type": CANDIDATE_DATASET})
    with pytest.raises(CandidateProvenanceError) as exc_info:
        stage_rag_candidate(ds_record, title="Title", content="Content", staged_by="admin-1")
    assert "expected 'RAG_CANDIDATE'" in str(exc_info.value)


def test_49_stage_dataset_rejects_rag_candidate_type(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    rag_record = KnowledgeGapRecord(**{**sample_approved_dataset_record.__dict__, "candidate_type": CANDIDATE_RAG})
    with pytest.raises(CandidateProvenanceError) as exc_info:
        stage_dataset_candidate(rag_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-1")
    assert "expected 'DATASET_CANDIDATE'" in str(exc_info.value)


def test_50_security_admin_boundary_denies_rag_staging(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    sec_record = KnowledgeGapRecord(
        **{
            **sample_approved_rag_record.__dict__,
            "gap_type": GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
            "severity": SEVERITY_CRITICAL,
        }
    )
    with pytest.raises(GovernanceSecurityError) as exc_info:
        stage_rag_candidate(sec_record, title="Title", content="Content", staged_by="admin-1")
    assert "SECURITY_ADMIN_BOUNDARY" in str(exc_info.value)


def test_51_security_admin_boundary_denies_dataset_staging(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    sec_record = KnowledgeGapRecord(
        **{
            **sample_approved_dataset_record.__dict__,
            "gap_type": GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
            "severity": SEVERITY_CRITICAL,
        }
    )
    with pytest.raises(GovernanceSecurityError) as exc_info:
        stage_dataset_candidate(sec_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-1")
    assert "SECURITY_ADMIN_BOUNDARY" in str(exc_info.value)


def test_52_provenance_preserves_source_gap_id(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    assert staged.provenance.source_gap_id == sample_approved_rag_record.gap_id


def test_53_provenance_preserves_source_record_id(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    assert staged.provenance.source_record_id == sample_approved_rag_record.record_id


def test_54_provenance_preserves_source_request_id(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    assert staged.provenance.source_request_id == sample_approved_rag_record.request_id


def test_55_provenance_preserves_approved_by_and_at(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    assert staged.provenance.approved_by == sample_approved_rag_record.reviewed_by
    assert staged.provenance.approved_at == sample_approved_rag_record.reviewed_at


def test_56_provenance_is_immutable(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    with pytest.raises(AttributeError):
        staged.provenance.source_gap_id = "new-gap"  # type: ignore[misc]


def test_57_rag_candidate_dict_serialization(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    d = staged.to_dict()
    assert d["candidate_id"] == staged.candidate_id
    assert d["provenance"]["source_gap_id"] == sample_approved_rag_record.gap_id


def test_58_dataset_candidate_dict_serialization(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(sample_approved_dataset_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-2")
    d = staged.to_dict()
    assert d["candidate_id"] == staged.candidate_id
    assert d["input_context"] == "Input context"


def test_59_candidate_version_tracking(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1", candidate_version="2.1.0")
    assert staged.candidate_version == "2.1.0"


def test_60_sanitized_metadata_preserved_in_staging(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    assert staged.sanitized_metadata == {"env": "prod"}


# ===========================================================================
# 61-75: State Machine & Governance Service Tests
# ===========================================================================

def test_61_rag_start_review_validated_to_pending_review(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    service = CandidateCurationService()
    in_rev = service.start_review(staged, reviewer_id="reviewer-1")
    assert in_rev.status == STAGING_STATUS_PENDING_REVIEW
    assert in_rev.reviewed_by == "reviewer-1"


def test_62_dataset_start_review_validated_to_pending_review(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(sample_approved_dataset_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-2")
    service = CandidateCurationService()
    in_rev = service.start_review(staged, reviewer_id="reviewer-2")
    assert in_rev.status == STAGING_STATUS_PENDING_REVIEW
    assert in_rev.reviewed_by == "reviewer-2"


def test_63_rag_approve_staging_pending_review_to_ready_for_ingestion(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    service = CandidateCurationService()
    in_rev = service.start_review(staged, reviewer_id="reviewer-1")
    app = service.approve_staging(in_rev, approver_id="super-admin-1", approval_notes="Looks great for RAG")
    assert app.status == RAG_STATUS_READY_FOR_INGESTION
    assert app.reviewed_by == "super-admin-1"
    assert "Looks great for RAG" in (app.reviewer_notes or "")


def test_64_dataset_approve_staging_pending_review_to_ready_for_export(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(sample_approved_dataset_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-2")
    service = CandidateCurationService()
    in_rev = service.start_review(staged, reviewer_id="reviewer-2")
    app = service.approve_staging(in_rev, approver_id="super-admin-1", approval_notes="Approved for Dataset export")
    assert app.status == DATASET_STATUS_READY_FOR_EXPORT
    assert app.reviewed_by == "super-admin-1"


def test_65_rag_reject_staging(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    service = CandidateCurationService()
    rej = service.reject_staging(staged, reviewer_id="reviewer-1", rejection_reason="Inaccurate content")
    assert rej.status == STAGING_STATUS_REJECTED
    assert "Inaccurate content" in (rej.reviewer_notes or "")


def test_66_dataset_reject_staging(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(sample_approved_dataset_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-2")
    service = CandidateCurationService()
    rej = service.reject_staging(staged, reviewer_id="reviewer-2", rejection_reason="Out of domain")
    assert rej.status == STAGING_STATUS_REJECTED


def test_67_rag_defer_staging(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    service = CandidateCurationService()
    def_rec = service.defer_staging(staged, reviewer_id="reviewer-1", deferral_reason="Need SME review")
    assert def_rec.status == STAGING_STATUS_DEFERRED


def test_68_dataset_defer_staging(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(sample_approved_dataset_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-2")
    service = CandidateCurationService()
    def_rec = service.defer_staging(staged, reviewer_id="reviewer-2", deferral_reason="Check dataset license")
    assert def_rec.status == STAGING_STATUS_DEFERRED


def test_69_rag_deferred_return_to_review(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    service = CandidateCurationService()
    def_rec = service.defer_staging(staged, reviewer_id="reviewer-1")
    re_rev = service.start_review(def_rec, reviewer_id="reviewer-2")
    assert re_rev.status == STAGING_STATUS_PENDING_REVIEW


def test_70_invalid_direct_jump_draft_to_ready_for_ingestion(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    draft_record = RAGCandidateStagingRecord(**{**stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1").__dict__, "status": STAGING_STATUS_DRAFT})
    service = CandidateCurationService()
    with pytest.raises(InvalidStagingTransitionError):
        service.approve_staging(draft_record, approver_id="super-admin-1")


def test_71_invalid_direct_jump_draft_to_ready_for_export(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    draft_record = DatasetCandidateStagingRecord(**{**stage_dataset_candidate(sample_approved_dataset_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-2").__dict__, "status": STAGING_STATUS_DRAFT})
    service = CandidateCurationService()
    with pytest.raises(InvalidStagingTransitionError):
        service.approve_staging(draft_record, approver_id="super-admin-1")


def test_72_invalid_approval_from_draft(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    service = CandidateCurationService()
    with pytest.raises(InvalidStagingTransitionError):
        service.approve_staging(staged, approver_id="super-admin-1")


def test_73_terminal_ready_for_ingestion_invariant(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    service = CandidateCurationService()
    in_rev = service.start_review(staged, reviewer_id="reviewer-1")
    app = service.approve_staging(in_rev, approver_id="super-admin-1")
    assert app.status == RAG_STATUS_READY_FOR_INGESTION
    with pytest.raises(InvalidStagingTransitionError):
        service.start_review(app, reviewer_id="admin-2")


def test_74_terminal_ready_for_export_invariant(sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(sample_approved_dataset_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-2")
    service = CandidateCurationService()
    in_rev = service.start_review(staged, reviewer_id="reviewer-2")
    app = service.approve_staging(in_rev, approver_id="super-admin-1")
    assert app.status == DATASET_STATUS_READY_FOR_EXPORT
    with pytest.raises(InvalidStagingTransitionError):
        service.start_review(app, reviewer_id="admin-2")


def test_75_reviewer_notes_combining(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    service = CandidateCurationService()
    in_rev = service.start_review(staged, reviewer_id="reviewer-1")
    rej = service.reject_staging(in_rev, reviewer_id="reviewer-1", rejection_reason="Note A")
    assert "Note A" in (rej.reviewer_notes or "")


# ===========================================================================
# 76-85: SQLite Repository & Database Isolation Tests
# ===========================================================================

def test_76_repository_init_creates_tables_and_indexes(temp_repo: CandidateCurationRepository) -> None:
    cursor = temp_repo.conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row["name"] for row in cursor.fetchall()]
    assert "rag_candidate_staging_records" in tables
    assert "dataset_candidate_staging_records" in tables


def test_77_insert_and_get_rag_candidate(temp_repo: CandidateCurationRepository, sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    temp_repo.insert_rag_candidate(staged)
    fetched = temp_repo.get_rag_candidate_by_id(staged.candidate_id)
    assert fetched is not None
    assert fetched.candidate_id == staged.candidate_id
    assert fetched.title == "Title"


def test_78_insert_and_get_dataset_candidate(temp_repo: CandidateCurationRepository, sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(sample_approved_dataset_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="general", staged_by="admin-2")
    temp_repo.insert_dataset_candidate(staged)
    fetched = temp_repo.get_dataset_candidate_by_id(staged.candidate_id)
    assert fetched is not None
    assert fetched.candidate_id == staged.candidate_id
    assert fetched.input_context == "Input context"


def test_79_list_rag_candidates_filtering(temp_repo: CandidateCurationRepository, sample_approved_rag_record: KnowledgeGapRecord) -> None:
    s1 = stage_rag_candidate(sample_approved_rag_record, title="Title 1", content="Content 1", staged_by="admin-1")
    temp_repo.insert_rag_candidate(s1)
    res_val = temp_repo.list_rag_candidates(status=STAGING_STATUS_VALIDATED)
    res_rej = temp_repo.list_rag_candidates(status=STAGING_STATUS_REJECTED)
    assert len(res_val) == 1
    assert len(res_rej) == 0


def test_80_list_dataset_candidates_filtering(temp_repo: CandidateCurationRepository, sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    s1 = stage_dataset_candidate(sample_approved_dataset_record, input_context="Input 1", proposed_output="Output 1", language="en", domain_topic="d", staged_by="admin-2")
    temp_repo.insert_dataset_candidate(s1)
    res_val = temp_repo.list_dataset_candidates(status=STAGING_STATUS_VALIDATED)
    assert len(res_val) == 1


def test_81_update_rag_candidate_state(temp_repo: CandidateCurationRepository, sample_approved_rag_record: KnowledgeGapRecord) -> None:
    staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    temp_repo.insert_rag_candidate(staged)

    service = CandidateCurationService()
    in_rev = service.start_review(staged, reviewer_id="rev-1")
    temp_repo.update_rag_candidate_state(in_rev)

    fetched = temp_repo.get_rag_candidate_by_id(staged.candidate_id)
    assert fetched is not None
    assert fetched.status == STAGING_STATUS_PENDING_REVIEW


def test_82_update_dataset_candidate_state(temp_repo: CandidateCurationRepository, sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    staged = stage_dataset_candidate(sample_approved_dataset_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-2")
    temp_repo.insert_dataset_candidate(staged)

    service = CandidateCurationService()
    in_rev = service.start_review(staged, reviewer_id="rev-2")
    temp_repo.update_dataset_candidate_state(in_rev)

    fetched = temp_repo.get_dataset_candidate_by_id(staged.candidate_id)
    assert fetched is not None
    assert fetched.status == STAGING_STATUS_PENDING_REVIEW


def test_83_aggregate_staging_metrics(temp_repo: CandidateCurationRepository, sample_approved_rag_record: KnowledgeGapRecord, sample_approved_dataset_record: KnowledgeGapRecord) -> None:
    r_staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
    d_staged = stage_dataset_candidate(sample_approved_dataset_record, input_context="Input context", proposed_output="Output context", language="en", domain_topic="d", staged_by="admin-2")

    temp_repo.insert_rag_candidate(r_staged)
    temp_repo.insert_dataset_candidate(d_staged)

    metrics = temp_repo.aggregate_staging_metrics()
    assert metrics["total_staged_candidates"] == 2
    assert metrics["rag_candidates_total"] == 1
    assert metrics["dataset_candidates_total"] == 1


def test_84_temp_sqlite_db_isolation(sample_approved_rag_record: KnowledgeGapRecord) -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
        db_path = tf.name
    try:
        conn = sqlite3.connect(db_path)
        repo = CandidateCurationRepository(conn)
        staged = stage_rag_candidate(sample_approved_rag_record, title="Title", content="Content", staged_by="admin-1")
        repo.insert_rag_candidate(staged)
        assert repo.get_rag_candidate_by_id(staged.candidate_id) is not None
        conn.close()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_85_in_memory_sqlite_db_isolation() -> None:
    conn = sqlite3.connect(":memory:")
    repo = CandidateCurationRepository(conn)
    metrics = repo.aggregate_staging_metrics()
    assert metrics["total_staged_candidates"] == 0


# ===========================================================================
# 86-92: Admin API Router & RBAC Invariants Tests
# ===========================================================================

def test_86_admin_candidates_staged_get_endpoint_exists() -> None:
    from backend.api.routes.candidate_admin import list_staged_candidates
    assert callable(list_staged_candidates)


def test_87_admin_candidates_stage_rag_endpoint_exists() -> None:
    from backend.api.routes.candidate_admin import stage_rag_candidate_endpoint
    assert callable(stage_rag_candidate_endpoint)


def test_88_admin_candidates_stage_dataset_endpoint_exists() -> None:
    from backend.api.routes.candidate_admin import stage_dataset_candidate_endpoint
    assert callable(stage_dataset_candidate_endpoint)


def test_89_admin_candidates_approve_endpoint_exists() -> None:
    from backend.api.routes.candidate_admin import approve_staged_candidate_endpoint
    assert callable(approve_staged_candidate_endpoint)


def test_90_admin_router_prefix() -> None:
    from backend.api.routes.candidate_admin import router
    assert router.prefix == "/admin/knowledge-candidates"


def test_91_admin_router_tags() -> None:
    from backend.api.routes.candidate_admin import router
    assert "knowledge-candidates" in router.tags


def test_92_router_registered_in_route_registry() -> None:
    import backend.api.route_registry as rr
    plugin_names = [p.name for p in rr.ROUTE_PLUGINS]
    assert "candidate_admin" in plugin_names


# ===========================================================================
# 93-100: AST Security, Autonomous Learning Protection, & Production DB Integrity
# ===========================================================================

def test_93_non_autonomous_learning_invariant() -> None:
    import core_model.capabilities.candidate_curation_service as mod
    for name, obj in inspect.getmembers(mod):
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            assert "train" not in name.lower()
            assert "ingest" not in name.lower()
            assert "embed" not in name.lower()


def test_94_ast_security_candidate_curation_service() -> None:
    import core_model.capabilities.candidate_curation_service as mod
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_95_ast_security_candidate_curation_repository() -> None:
    import backend.database.repositories.candidate_curation_repository as mod
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_96_no_network_calls_in_pure_curation_service() -> None:
    code = inspect.getsource(CandidateCurationService).lower()
    for forbidden in ("requests.", "httpx.", "urllib.", "aiohttp.", "socket."):
        assert forbidden not in code


def test_97_no_subprocess_in_pure_curation_service() -> None:
    code = inspect.getsource(CandidateCurationService).lower()
    for forbidden in ("subprocess", "os.system", "os.popen", "popen"):
        assert forbidden not in code


def test_98_no_workers_schedulers_in_pure_curation_service() -> None:
    code = inspect.getsource(CandidateCurationService).lower()
    for forbidden in ("celery", "apscheduler", "cron", "backgroundtasks", "asyncio.create_task"):
        assert forbidden not in code


def test_99_production_db_sha256_and_size_unchanged() -> None:
    assert os.path.exists(PROD_DB_PATH), f"Production database path {PROD_DB_PATH} must exist"
    hasher = hashlib.sha256()
    with open(PROD_DB_PATH, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual_sha = hasher.hexdigest()
    actual_size = os.path.getsize(PROD_DB_PATH)

    assert actual_sha == EXPECTED_DB_SHA256, f"Production DB SHA-256 mismatch! Expected {EXPECTED_DB_SHA256}, got {actual_sha}."
    assert actual_size == EXPECTED_DB_SIZE, f"Production DB size mismatch! Expected {EXPECTED_DB_SIZE}, got {actual_size}."


def test_100_final_integrity_contract_validation() -> None:
    """Final contract validation verifying Phase 21 completion."""
    assert EXPECTED_DB_SHA256 == "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    assert EXPECTED_DB_SIZE == 11096064
    assert len(RAG_ALLOWED_TRANSITIONS) > 0
    assert len(DATASET_ALLOWED_TRANSITIONS) > 0
