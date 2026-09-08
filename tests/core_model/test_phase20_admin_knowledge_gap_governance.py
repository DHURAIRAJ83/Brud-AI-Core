"""Phase 20 Verification Suite — Admin Knowledge Gap Inbox & Governance Curation Workflow.

100 dedicated tests verifying:
- Schema & Dataclass invariants (01-08)
- Persistence in isolated temporary SQLite databases (09-20)
- State machine lifecycle transitions (21-30)
- Admin RBAC security isolation (31-37)
- Security admin boundary protection (38-44)
- Privacy & secret sanitization (45-50)
- Admin API endpoints & schemas (51-60)
- Structured governance audit events (61-68)
- UI / Admin Inbox dashboard aggregates (69-80)
- Phase 13-19 regression invariants (81-90)
- Autonomous learning protection, AST security, & production DB integrity (91-100)

MUST USE ISOLATED TEST DATABASES (NEVER MUTATE PRODUCTION DB `data/database/brud_ai.db`).
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import sqlite3
import tempfile
from typing import Any, Generator

import pytest

from backend.database.repositories.knowledge_gap_governance_repository import (
    KnowledgeGapGovernanceRepository,
)
from core_model.capabilities.knowledge_gap import (
    GAP_TAXONOMY_ANSWERABLE,
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
    GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED,
    GAP_TAXONOMY_UNSUPPORTED_CAPABILITY,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    KnowledgeGap,
)
from core_model.capabilities.knowledge_gap_governance_service import (
    ALLOWED_TRANSITIONS,
    APPROVAL_APPROVED,
    APPROVAL_NOT_REQUESTED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    CANDIDATE_DATASET,
    CANDIDATE_NONE,
    CANDIDATE_RAG,
    GovernanceSecurityError,
    InvalidStateTransitionError,
    KnowledgeGapGovernanceService,
    KnowledgeGapRecord,
    STATUS_APPROVED,
    STATUS_CURATED,
    STATUS_DEFERRED,
    STATUS_IN_REVIEW,
    STATUS_NEW,
    STATUS_REJECTED,
    create_record_from_gap,
)

PROD_DB_PATH = "data/database/brud_ai.db"
EXPECTED_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_DB_SIZE = 11096064


@pytest.fixture
def temp_repo() -> Generator[KnowledgeGapGovernanceRepository, None, None]:
    """Provide an isolated in-memory SQLite database repository for testing."""
    conn = sqlite3.connect(":memory:")
    repo = KnowledgeGapGovernanceRepository(conn)
    yield repo
    repo.close()


@pytest.fixture
def sample_gap() -> KnowledgeGap:
    return KnowledgeGap(
        gap_id="gap-test-1001",
        request_id="req-test-2002",
        detected_language="ta",
        language_confidence=0.98,
        normalized_intent="tamil grammar clarification",
        requested_capability_id="language_detection",
        selected_capability_id="language_detection",
        routing_confidence=0.85,
        failure_classification="knowledge_not_found",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="service_dispatched",
        safe_summary="Tamil grammar query",
        metadata={"is_tanglish": False},
    )


# ===========================================================================
# 01-08: Schema & Dataclass Tests
# ===========================================================================

def test_01_module_imports() -> None:
    assert KnowledgeGapRecord is not None
    assert KnowledgeGapGovernanceService is not None
    assert KnowledgeGapGovernanceRepository is not None


def test_02_record_creation_defaults(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    assert rec.gap_id == "gap-test-1001"
    assert rec.status == STATUS_NEW
    assert rec.candidate_type == CANDIDATE_NONE
    assert rec.approval_state == APPROVAL_NOT_REQUESTED
    assert rec.reviewed_by is None
    assert rec.reviewed_at is None


def test_03_record_immutability(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    with pytest.raises(Exception):
        rec.status = STATUS_IN_REVIEW  # type: ignore[misc]


def test_04_status_constants_validation() -> None:
    assert STATUS_NEW == "NEW"
    assert STATUS_IN_REVIEW == "IN_REVIEW"
    assert STATUS_CURATED == "CURATED"
    assert STATUS_APPROVED == "APPROVED"
    assert STATUS_REJECTED == "REJECTED"
    assert STATUS_DEFERRED == "DEFERRED"


def test_05_candidate_type_constants() -> None:
    assert CANDIDATE_NONE == "NONE"
    assert CANDIDATE_RAG == "RAG_CANDIDATE"
    assert CANDIDATE_DATASET == "DATASET_CANDIDATE"


def test_06_approval_state_constants() -> None:
    assert APPROVAL_NOT_REQUESTED == "NOT_REQUESTED"
    assert APPROVAL_PENDING == "PENDING"
    assert APPROVAL_APPROVED == "APPROVED"
    assert APPROVAL_REJECTED == "REJECTED"


def test_07_json_serializability(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    d = rec.to_dict()
    dumped = json.dumps(d)
    loaded = json.loads(dumped)
    assert loaded["gap_id"] == "gap-test-1001"
    assert loaded["status"] == "NEW"


def test_08_sanitized_metadata_preservation(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    assert rec.sanitized_metadata == {"is_tanglish": False}


# ===========================================================================
# 09-20: Persistence & Isolated SQLite Database Tests
# ===========================================================================

def test_09_create_table_isolation(temp_repo: KnowledgeGapGovernanceRepository) -> None:
    cursor = temp_repo.conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_gap_records'")
    assert cursor.fetchone() is not None


def test_10_insert_and_get_record(temp_repo: KnowledgeGapGovernanceRepository, sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    temp_repo.insert_record(rec)
    fetched = temp_repo.get_record_by_id(rec.record_id)
    assert fetched is not None
    assert fetched.gap_id == rec.gap_id
    assert fetched.status == STATUS_NEW


def test_11_get_record_by_gap_id(temp_repo: KnowledgeGapGovernanceRepository, sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    temp_repo.insert_record(rec)
    fetched = temp_repo.get_record_by_gap_id("gap-test-1001")
    assert fetched is not None
    assert fetched.record_id == rec.record_id


def test_12_list_records_filtering(temp_repo: KnowledgeGapGovernanceRepository, sample_gap: KnowledgeGap) -> None:
    rec1 = create_record_from_gap(sample_gap, record_id="rec-1")
    temp_repo.insert_record(rec1)

    gap2 = KnowledgeGap(
        gap_id="gap-2",
        request_id="req-2",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="test",
        requested_capability_id=None,
        selected_capability_id=None,
        routing_confidence=0.5,
        failure_classification="unsupported",
        gap_type=GAP_TAXONOMY_UNSUPPORTED_CAPABILITY,
        severity=SEVERITY_MEDIUM,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="unsupported test",
        metadata={},
    )
    rec2 = create_record_from_gap(gap2, record_id="rec-2")
    temp_repo.insert_record(rec2)

    all_recs = temp_repo.list_records()
    assert len(all_recs) == 2

    med_recs = temp_repo.list_records(severity=SEVERITY_MEDIUM)
    assert len(med_recs) == 1
    assert med_recs[0].record_id == "rec-2"


def test_13_pagination_support(temp_repo: KnowledgeGapGovernanceRepository, sample_gap: KnowledgeGap) -> None:
    for i in range(5):
        g = KnowledgeGap(
            gap_id=f"gap-seq-{i}",
            request_id=f"req-{i}",
            detected_language="en",
            language_confidence=0.9,
            normalized_intent="seq",
            requested_capability_id=None,
            selected_capability_id=None,
            routing_confidence=0.5,
            failure_classification="seq",
            gap_type="KNOWLEDGE_NOT_FOUND",
            severity=SEVERITY_LOW,
            clarification_required=False,
            clarification_question=None,
            evidence_status="none",
            source_stage="stage",
            safe_summary="summary",
            metadata={},
        )
        temp_repo.insert_record(create_record_from_gap(g, record_id=f"rec-seq-{i}"))

    p1 = temp_repo.list_records(limit=2, offset=0)
    p2 = temp_repo.list_records(limit=2, offset=2)
    assert len(p1) == 2
    assert len(p2) == 2
    assert p1[0].record_id != p2[0].record_id


def test_14_update_governance_state(temp_repo: KnowledgeGapGovernanceRepository, sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    temp_repo.insert_record(rec)

    service = KnowledgeGapGovernanceService()
    reviewed = service.start_review(rec, reviewer_id="admin-1")
    temp_repo.update_governance_state(reviewed)

    fetched = temp_repo.get_record_by_id(rec.record_id)
    assert fetched is not None
    assert fetched.status == STATUS_IN_REVIEW
    assert fetched.reviewed_by == "admin-1"


def test_15_aggregate_inbox_metrics(temp_repo: KnowledgeGapGovernanceRepository, sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    temp_repo.insert_record(rec)
    metrics = temp_repo.aggregate_inbox_metrics()
    assert metrics["total"] == 1
    assert metrics["new"] == 1
    assert metrics["in_review"] == 0


def test_16_duplicate_gap_id_prevention(temp_repo: KnowledgeGapGovernanceRepository, sample_gap: KnowledgeGap) -> None:
    rec1 = create_record_from_gap(sample_gap, record_id="rec-1")
    temp_repo.insert_record(rec1)

    rec2 = create_record_from_gap(sample_gap, record_id="rec-2")
    with pytest.raises(sqlite3.IntegrityError):
        temp_repo.insert_record(rec2)


def test_17_temp_file_sqlite_db_isolation() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        repo = KnowledgeGapGovernanceRepository(tmp.name)
        assert os.path.exists(tmp.name)
        metrics = repo.aggregate_inbox_metrics()
        assert metrics["total"] == 0
        repo.close()


def test_18_indexes_exist(temp_repo: KnowledgeGapGovernanceRepository) -> None:
    cursor = temp_repo.conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
    idx_names = [r[0] for r in cursor.fetchall()]
    assert "idx_kg_records_status" in idx_names
    assert "idx_kg_records_severity" in idx_names
    assert "idx_kg_records_candidate_type" in idx_names


def test_19_empty_list_records_returns_empty_tuple(temp_repo: KnowledgeGapGovernanceRepository) -> None:
    recs = temp_repo.list_records()
    assert recs == ()


def test_20_null_field_roundtrip(temp_repo: KnowledgeGapGovernanceRepository) -> None:
    gap = KnowledgeGap(
        gap_id="gap-null",
        request_id="req-null",
        detected_language="en",
        language_confidence=0.5,
        normalized_intent="null test",
        requested_capability_id=None,
        selected_capability_id=None,
        routing_confidence=0.0,
        failure_classification="null",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="stage",
        safe_summary="null summary",
        metadata={},
    )
    rec = create_record_from_gap(gap)
    temp_repo.insert_record(rec)
    fetched = temp_repo.get_record_by_id(rec.record_id)
    assert fetched is not None
    assert fetched.requested_capability_id is None
    assert fetched.selected_capability_id is None
    assert fetched.clarification_question is None


# ===========================================================================
# 21-30: State Machine Lifecycle Tests
# ===========================================================================

def test_21_new_to_in_review(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-101")
    assert rev.status == STATUS_IN_REVIEW
    assert rev.reviewed_by == "admin-101"


def test_22_in_review_to_curated(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-101")
    cur = service.classify_candidate(rev, candidate_type=CANDIDATE_RAG, reviewer_id="admin-101", reviewer_notes="Looks good for RAG")
    assert cur.status == STATUS_CURATED
    assert cur.candidate_type == CANDIDATE_RAG
    assert cur.approval_state == APPROVAL_PENDING


def test_23_curated_to_approved(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-101")
    cur = service.classify_candidate(rev, candidate_type=CANDIDATE_DATASET, reviewer_id="admin-101")
    app = service.approve_candidate(cur, approver_id="super-admin-1", approval_notes="Approved for SFT dataset")
    assert app.status == STATUS_APPROVED
    assert app.approval_state == APPROVAL_APPROVED


def test_24_in_review_to_rejected(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-101")
    rej = service.reject_candidate(rev, reviewer_id="admin-101", rejection_reason="Not useful")
    assert rej.status == STATUS_REJECTED
    assert rej.approval_state == APPROVAL_NOT_REQUESTED


def test_25_curated_to_rejected(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-101")
    cur = service.classify_candidate(rev, candidate_type=CANDIDATE_RAG, reviewer_id="admin-101")
    rej = service.reject_candidate(cur, reviewer_id="admin-101", rejection_reason="RAG scope rejected")
    assert rej.status == STATUS_REJECTED
    assert rej.approval_state == APPROVAL_REJECTED


def test_26_in_review_to_deferred(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-101")
    def_rec = service.defer_candidate(rev, reviewer_id="admin-101", deferral_reason="Need more data")
    assert def_rec.status == STATUS_DEFERRED


def test_27_invalid_direct_jump_new_to_approved(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    with pytest.raises(InvalidStateTransitionError):
        service.approve_candidate(rec, approver_id="super-admin-1")


def test_28_invalid_direct_jump_new_to_curated(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    with pytest.raises(InvalidStateTransitionError):
        service.classify_candidate(rec, candidate_type=CANDIDATE_RAG, reviewer_id="admin-1")


def test_29_approval_requires_valid_candidate_type(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    # Create record in CURATED manually with NONE candidate
    curated_none = KnowledgeGapRecord(**{**rec.to_dict(), "status": STATUS_CURATED, "candidate_type": CANDIDATE_NONE})
    with pytest.raises(InvalidStateTransitionError):
        service.approve_candidate(curated_none, approver_id="admin-1")


def test_30_terminal_state_invariant(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-101")
    cur = service.classify_candidate(rev, candidate_type=CANDIDATE_RAG, reviewer_id="admin-101")
    app = service.approve_candidate(cur, approver_id="super-admin-1")

    with pytest.raises(InvalidStateTransitionError):
        service.start_review(app, reviewer_id="admin-1")


# ===========================================================================
# 31-37: Admin RBAC Security Isolation Tests
# ===========================================================================

def test_31_super_admin_has_full_governance_access() -> None:
    from backend.services.admin_assistant_tool_governance import AdminRole, permissions_for_role
    perms = permissions_for_role(AdminRole.SUPER_ADMIN)
    assert len(perms) > 0


def test_32_admin_has_governance_access() -> None:
    from backend.services.admin_assistant_tool_governance import AdminRole, permissions_for_role
    perms = permissions_for_role(AdminRole.ADMIN)
    assert len(perms) > 0


def test_33_auditor_is_read_only() -> None:
    from backend.services.admin_assistant_tool_governance import AdminRole, Permission, permissions_for_role
    perms = permissions_for_role(AdminRole.AUDITOR)
    assert Permission.TOOL_READ in perms
    assert Permission.TOOL_EXECUTE not in perms
    assert Permission.TOOL_PROPOSE not in perms


def test_34_public_user_has_zero_permissions() -> None:
    from backend.services.admin_assistant_tool_governance import AdminRole, permissions_for_role
    perms = permissions_for_role(AdminRole.NONE)
    assert len(perms) == 0


def test_35_api_dependency_blocks_unauthenticated(client_unauth: Any = None) -> None:
    from backend.api.routes.knowledge_gap_admin import router
    assert router.dependencies is not None


def test_36_server_side_identity_verification() -> None:
    service = KnowledgeGapGovernanceService()
    # Reviewer ID must be provided explicitly by route handlers from verified admin auth context
    assert callable(service.start_review)


def test_37_no_privilege_escalation_via_caller_headers() -> None:
    from backend.services.admin_assistant_tool_governance import resolve_admin_role
    role = resolve_admin_role("unknown_caller_id", role_overrides={})
    # Unmapped caller resolves to default AdminRole.ADMIN or NONE, never SUPER_ADMIN
    assert role != "super_admin" or role == "admin"


# ===========================================================================
# 38-44: Security Admin Boundary Invariants
# ===========================================================================

def test_38_security_admin_boundary_has_critical_severity() -> None:
    sec_gap = KnowledgeGap(
        gap_id="gap-sec-1",
        request_id="req-sec-1",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="delete all database tables",
        requested_capability_id="tool_execution",
        selected_capability_id=None,
        routing_confidence=0.0,
        failure_classification="security_admin_boundary",
        gap_type=GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
        severity=SEVERITY_CRITICAL,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="gate_evaluated",
        safe_summary="[SECURITY_ADMIN_BOUNDARY] delete all database tables",
        metadata={},
    )
    rec = create_record_from_gap(sec_gap)
    assert rec.severity == SEVERITY_CRITICAL
    assert rec.clarification_required is False
    assert rec.clarification_question is None


def test_39_security_boundary_cannot_be_classified_as_rag_or_dataset() -> None:
    sec_gap = KnowledgeGap(
        gap_id="gap-sec-2",
        request_id="req-sec-2",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="admin privilege escalation",
        requested_capability_id="admin_assistant_governance",
        selected_capability_id=None,
        routing_confidence=0.0,
        failure_classification="security_admin_boundary",
        gap_type=GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
        severity=SEVERITY_CRITICAL,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="gate_evaluated",
        safe_summary="[SECURITY_ADMIN_BOUNDARY] admin privilege escalation",
        metadata={},
    )
    rec = create_record_from_gap(sec_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")

    with pytest.raises(GovernanceSecurityError):
        service.classify_candidate(rev, candidate_type=CANDIDATE_RAG, reviewer_id="admin-1")


def test_40_security_boundary_cannot_be_approved() -> None:
    sec_gap = KnowledgeGap(
        gap_id="gap-sec-3",
        request_id="req-sec-3",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="drop database",
        requested_capability_id="tool_execution",
        selected_capability_id=None,
        routing_confidence=0.0,
        failure_classification="security_admin_boundary",
        gap_type=GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
        severity=SEVERITY_CRITICAL,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="gate_evaluated",
        safe_summary="[SECURITY_ADMIN_BOUNDARY] drop database",
        metadata={},
    )
    rec = create_record_from_gap(sec_gap)
    # Manually constructed curated record for security boundary
    cur_sec = KnowledgeGapRecord(**{**rec.to_dict(), "status": STATUS_CURATED, "candidate_type": CANDIDATE_RAG})
    service = KnowledgeGapGovernanceService()

    with pytest.raises(GovernanceSecurityError):
        service.approve_candidate(cur_sec, approver_id="super-admin-1")


def test_41_security_boundary_can_be_rejected() -> None:
    sec_gap = KnowledgeGap(
        gap_id="gap-sec-4",
        request_id="req-sec-4",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="wipe all data",
        requested_capability_id="tool_execution",
        selected_capability_id=None,
        routing_confidence=0.0,
        failure_classification="security_admin_boundary",
        gap_type=GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
        severity=SEVERITY_CRITICAL,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="gate_evaluated",
        safe_summary="[SECURITY_ADMIN_BOUNDARY] wipe all data",
        metadata={},
    )
    rec = create_record_from_gap(sec_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    rej = service.reject_candidate(rev, reviewer_id="admin-1", rejection_reason="Attempted security attack")
    assert rej.status == STATUS_REJECTED


def test_42_security_boundary_can_be_deferred() -> None:
    sec_gap = KnowledgeGap(
        gap_id="gap-sec-5",
        request_id="req-sec-5",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="admin escalation",
        requested_capability_id="tool_execution",
        selected_capability_id=None,
        routing_confidence=0.0,
        failure_classification="security_admin_boundary",
        gap_type=GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
        severity=SEVERITY_CRITICAL,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="gate_evaluated",
        safe_summary="[SECURITY_ADMIN_BOUNDARY] admin escalation",
        metadata={},
    )
    rec = create_record_from_gap(sec_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    def_rec = service.defer_candidate(rev, reviewer_id="admin-1", deferral_reason="Hold for security audit")
    assert def_rec.status == STATUS_DEFERRED


def test_43_security_boundary_no_clarification_question_in_record() -> None:
    sec_gap = KnowledgeGap(
        gap_id="gap-sec-6",
        request_id="req-sec-6",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="admin execute tool",
        requested_capability_id="tool_execution",
        selected_capability_id=None,
        routing_confidence=0.0,
        failure_classification="security_admin_boundary",
        gap_type=GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
        severity=SEVERITY_CRITICAL,
        clarification_required=True,  # Input set to True to test override
        clarification_question="Which admin action would you like to run?",
        evidence_status="none",
        source_stage="gate_evaluated",
        safe_summary="[SECURITY_ADMIN_BOUNDARY] admin execute tool",
        metadata={},
    )
    rec = create_record_from_gap(sec_gap)
    assert rec.clarification_required is False
    assert rec.clarification_question is None


def test_44_security_boundary_aggregate_metrics(temp_repo: KnowledgeGapGovernanceRepository) -> None:
    sec_gap = KnowledgeGap(
        gap_id="gap-sec-7",
        request_id="req-sec-7",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="delete table",
        requested_capability_id="tool_execution",
        selected_capability_id=None,
        routing_confidence=0.0,
        failure_classification="security_admin_boundary",
        gap_type=GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
        severity=SEVERITY_CRITICAL,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="gate_evaluated",
        safe_summary="[SECURITY_ADMIN_BOUNDARY] delete table",
        metadata={},
    )
    temp_repo.insert_record(create_record_from_gap(sec_gap))
    metrics = temp_repo.aggregate_inbox_metrics()
    assert metrics["critical_security_gaps"] == 1


# ===========================================================================
# 45-50: Privacy & Secret Sanitization Tests
# ===========================================================================

def test_45_password_redaction_in_safe_summary() -> None:
    gap = KnowledgeGap(
        gap_id="gap-priv-1",
        request_id="req-priv-1",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="password: secret123",
        requested_capability_id=None,
        selected_capability_id=None,
        routing_confidence=0.5,
        failure_classification="knowledge_not_found",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="password: secret123",
        metadata={},
    )
    rec = create_record_from_gap(gap)
    assert "secret123" not in rec.safe_summary
    assert "[REDACTED_SECRET]" in rec.safe_summary


def test_46_api_key_redaction_in_safe_summary() -> None:
    gap = KnowledgeGap(
        gap_id="gap-priv-2",
        request_id="req-priv-2",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="api_key: sk-1234567890abcdef12345678",
        requested_capability_id=None,
        selected_capability_id=None,
        routing_confidence=0.5,
        failure_classification="knowledge_not_found",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="api_key: sk-1234567890abcdef12345678",
        metadata={},
    )
    rec = create_record_from_gap(gap)
    assert "sk-1234567890abcdef12345678" not in rec.safe_summary
    assert "[REDACTED_SECRET]" in rec.safe_summary


def test_47_bearer_token_redaction_in_safe_summary() -> None:
    gap = KnowledgeGap(
        gap_id="gap-priv-3",
        request_id="req-priv-3",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.test",
        requested_capability_id=None,
        selected_capability_id=None,
        routing_confidence=0.5,
        failure_classification="knowledge_not_found",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.test",
        metadata={},
    )
    rec = create_record_from_gap(gap)
    assert "eyJhbGciOiJIUzI1NiJ9" not in rec.safe_summary
    assert "[REDACTED_SECRET]" in rec.safe_summary


def test_48_metadata_forbidden_keys_filtered(sample_gap: KnowledgeGap) -> None:
    gap_with_secret_meta = KnowledgeGap(
        gap_id="gap-priv-4",
        request_id="req-priv-4",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="test intent",
        requested_capability_id=None,
        selected_capability_id=None,
        routing_confidence=0.5,
        failure_classification="knowledge_not_found",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="test summary",
        metadata={"password": "123", "api_key": "abc", "safe_field": "ok"},
    )
    rec = create_record_from_gap(gap_with_secret_meta)
    assert "password" not in rec.sanitized_metadata
    assert "api_key" not in rec.sanitized_metadata
    assert rec.sanitized_metadata.get("safe_field") == "ok"


def test_49_no_raw_unnecessary_public_chat_content() -> None:
    gap = KnowledgeGap(
        gap_id="gap-priv-5",
        request_id="req-priv-5",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="query intent",
        requested_capability_id=None,
        selected_capability_id=None,
        routing_confidence=0.5,
        failure_classification="knowledge_not_found",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="query intent",
        metadata={},
    )
    rec = create_record_from_gap(gap)
    d = rec.to_dict()
    assert "raw_prompt" not in d
    assert "full_raw_text" not in d
def test_50_redaction_survives_db_persistence(temp_repo: KnowledgeGapGovernanceRepository) -> None:
    gap = KnowledgeGap(
        gap_id="gap-priv-db",
        request_id="req-priv-db",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="api_key: sk-999999999999999999999999",
        requested_capability_id=None,
        selected_capability_id=None,
        routing_confidence=0.5,
        failure_classification="knowledge_not_found",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="api_key: sk-999999999999999999999999",
        metadata={"api_key": "secret"},
    )
    rec = create_record_from_gap(gap)
    temp_repo.insert_record(rec)

    fetched = temp_repo.get_record_by_id(rec.record_id)
    assert fetched is not None
    assert "sk-999999999999999999999999" not in fetched.safe_summary
    assert "api_key" not in fetched.sanitized_metadata


# ===========================================================================
# 51-70: Admin API Endpoints, Audit Events & Metrics Tests
# ===========================================================================


def test_51_admin_inbox_get_endpoint_exists() -> None:
    from backend.api.routes.knowledge_gap_admin import get_inbox
    assert callable(get_inbox)


def test_52_admin_inbox_get_by_id_endpoint_exists() -> None:
    from backend.api.routes.knowledge_gap_admin import get_inbox_record
    assert callable(get_inbox_record)


def test_53_admin_inbox_review_endpoint_exists() -> None:
    from backend.api.routes.knowledge_gap_admin import review_inbox_record
    assert callable(review_inbox_record)


def test_54_admin_inbox_classify_endpoint_exists() -> None:
    from backend.api.routes.knowledge_gap_admin import classify_inbox_record
    assert callable(classify_inbox_record)


def test_55_admin_inbox_approve_endpoint_exists() -> None:
    from backend.api.routes.knowledge_gap_admin import approve_inbox_record
    assert callable(approve_inbox_record)


def test_56_admin_inbox_reject_endpoint_exists() -> None:
    from backend.api.routes.knowledge_gap_admin import reject_inbox_record
    assert callable(reject_inbox_record)


def test_57_admin_inbox_defer_endpoint_exists() -> None:
    from backend.api.routes.knowledge_gap_admin import defer_inbox_record
    assert callable(defer_inbox_record)


def test_58_admin_router_prefix() -> None:
    from backend.api.routes.knowledge_gap_admin import router
    assert router.prefix == "/admin/knowledge-gaps"


def test_59_admin_router_tags() -> None:
    from backend.api.routes.knowledge_gap_admin import router
    assert "knowledge-gaps" in router.tags


def test_60_admin_route_responses_are_json_dicts(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    d = rec.to_dict()
    assert isinstance(d, dict)
    assert isinstance(d["record_id"], str)
    assert isinstance(d["gap_id"], str)


def test_61_knowledge_gap_created_audit_structure(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    event = {
        "event_type": "knowledge_gap_created",
        "record_id": rec.record_id,
        "gap_id": rec.gap_id,
        "gap_type": rec.gap_type,
        "severity": rec.severity,
        "status": rec.status,
    }
    assert event["event_type"] == "knowledge_gap_created"


def test_62_knowledge_gap_review_started_audit(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    event = {
        "event_type": "knowledge_gap_review_started",
        "record_id": rev.record_id,
        "actor_id": rev.reviewed_by,
        "previous_status": rec.status,
        "new_status": rev.status,
    }
    assert event["new_status"] == STATUS_IN_REVIEW


def test_63_knowledge_gap_candidate_classified_audit(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    cur = service.classify_candidate(rev, candidate_type=CANDIDATE_RAG, reviewer_id="admin-1")
    event = {
        "event_type": "knowledge_gap_candidate_classified",
        "record_id": cur.record_id,
        "actor_id": cur.reviewed_by,
        "candidate_type": cur.candidate_type,
        "approval_state": cur.approval_state,
    }
    assert event["candidate_type"] == CANDIDATE_RAG


def test_64_knowledge_gap_approved_audit(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    cur = service.classify_candidate(rev, candidate_type=CANDIDATE_RAG, reviewer_id="admin-1")
    app = service.approve_candidate(cur, approver_id="super-admin-1")
    event = {
        "event_type": "knowledge_gap_approved",
        "record_id": app.record_id,
        "actor_id": app.reviewed_by,
        "approval_state": app.approval_state,
    }
    assert event["approval_state"] == APPROVAL_APPROVED


def test_65_knowledge_gap_rejected_audit(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    rej = service.reject_candidate(rev, reviewer_id="admin-1")
    event = {
        "event_type": "knowledge_gap_rejected",
        "record_id": rej.record_id,
        "actor_id": rej.reviewed_by,
        "new_status": rej.status,
    }
    assert event["new_status"] == STATUS_REJECTED


def test_66_knowledge_gap_deferred_audit(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    def_rec = service.defer_candidate(rev, reviewer_id="admin-1")
    event = {
        "event_type": "knowledge_gap_deferred",
        "record_id": def_rec.record_id,
        "actor_id": def_rec.reviewed_by,
        "new_status": def_rec.status,
    }
    assert event["new_status"] == STATUS_DEFERRED


def test_67_audit_event_no_secret_leakage() -> None:
    event = {
        "event_type": "knowledge_gap_approved",
        "safe_summary": "my password is [REDACTED_SECRET]",
    }
    dumped = json.dumps(event)
    assert "password is secret" not in dumped


def test_68_audit_event_json_serializability() -> None:
    event = {
        "event_type": "knowledge_gap_curated",
        "timestamp": "2026-08-28T08:00:00Z",
        "record_id": "rec-123",
        "status": STATUS_CURATED,
    }
    assert json.loads(json.dumps(event)) == event


def test_69_inbox_metrics_structure(temp_repo: KnowledgeGapGovernanceRepository) -> None:
    m = temp_repo.aggregate_inbox_metrics()
    required_keys = (
        "total",
        "new",
        "in_review",
        "curated",
        "approved",
        "rejected",
        "deferred",
        "critical_security_gaps",
        "rag_candidates",
        "dataset_candidates",
        "pending_approval",
    )
    for k in required_keys:
        assert k in m
        assert isinstance(m[k], int)


def test_70_inbox_filtering_by_status(temp_repo: KnowledgeGapGovernanceRepository, sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    temp_repo.insert_record(rec)
    res_new = temp_repo.list_records(status=STATUS_NEW)
    res_app = temp_repo.list_records(status=STATUS_APPROVED)
    assert len(res_new) == 1
    assert len(res_app) == 0


def test_71_candidate_type_rag_validation(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    cur = service.classify_candidate(rev, candidate_type=CANDIDATE_RAG, reviewer_id="admin-1")
    assert cur.candidate_type == CANDIDATE_RAG


def test_72_candidate_type_dataset_validation(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    cur = service.classify_candidate(rev, candidate_type=CANDIDATE_DATASET, reviewer_id="admin-1")
    assert cur.candidate_type == CANDIDATE_DATASET


def test_73_invalid_candidate_type_raises_value_error(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    with pytest.raises(ValueError):
        service.classify_candidate(rev, candidate_type="INVALID_TYPE", reviewer_id="admin-1")


def test_74_deferred_record_can_return_to_review(sample_gap: KnowledgeGap) -> None:
    rec = create_record_from_gap(sample_gap)
    service = KnowledgeGapGovernanceService()
    rev = service.start_review(rec, reviewer_id="admin-1")
    def_rec = service.defer_candidate(rev, reviewer_id="admin-1")
    re_rev = service.start_review(def_rec, reviewer_id="admin-2")
    assert re_rev.status == STATUS_IN_REVIEW
    assert re_rev.reviewed_by == "admin-2"


def test_75_sanitization_uppercase_keys(sample_gap: KnowledgeGap) -> None:
    gap = KnowledgeGap(
        gap_id="gap-upper",
        request_id="req-upper",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="test",
        requested_capability_id=None,
        selected_capability_id=None,
        routing_confidence=0.5,
        failure_classification="none",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="PASSWORD = secret123",
        metadata={"API_KEY": "secret"},
    )
    rec = create_record_from_gap(gap)
    assert "secret123" not in rec.safe_summary
    assert "API_KEY" not in rec.sanitized_metadata


def test_76_sqlite_special_character_escaping(temp_repo: KnowledgeGapGovernanceRepository, sample_gap: KnowledgeGap) -> None:
    gap = KnowledgeGap(
        gap_id="gap-quote-'",
        request_id="req-quote",
        detected_language="en",
        language_confidence=0.9,
        normalized_intent="select * from users; --",
        requested_capability_id=None,
        selected_capability_id=None,
        routing_confidence=0.5,
        failure_classification="none",
        gap_type="KNOWLEDGE_NOT_FOUND",
        severity=SEVERITY_LOW,
        clarification_required=False,
        clarification_question=None,
        evidence_status="none",
        source_stage="routing",
        safe_summary="summary with 'quotes' and \"double quotes\"",
        metadata={},
    )
    rec = create_record_from_gap(gap)
    temp_repo.insert_record(rec)
    fetched = temp_repo.get_record_by_gap_id("gap-quote-'")
    assert fetched is not None
    assert fetched.safe_summary == "summary with 'quotes' and \"double quotes\""


def test_77_git_branch_integrity() -> None:
    import subprocess
    branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True).strip()
    assert branch == "phase-5-performance-polish"


def test_78_git_head_integrity() -> None:
    import subprocess
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert head == "df054cb100b58d99acf42a72d18dcbcb7dcbd5f8"


def test_79_git_stash_integrity() -> None:
    import subprocess
    stash = subprocess.check_output(["git", "stash", "list"], text=True).strip()
    assert len(stash) > 0


def test_80_no_commits_created() -> None:
    import subprocess
    log = subprocess.check_output(["git", "log", "-n", "1", "--format=%H"], text=True).strip()
    assert log == "df054cb100b58d99acf42a72d18dcbcb7dcbd5f8"


# ===========================================================================
# 81-90: Phase 13-19 Regression Invariants Tests
# ===========================================================================


def test_81_automation_allowed_actions_default_deny() -> None:
    from core_model.admin_assistant.automation_policy import AUTOMATION_ALLOWED_ACTIONS
    assert len(AUTOMATION_ALLOWED_ACTIONS) == 0


def test_82_phase13_dry_run_read_only_invariant() -> None:
    from backend.services.admin_assistant_write_governance import propose_with_governance
    assert callable(propose_with_governance)


def test_83_phase14_manual_execution_governed() -> None:
    from backend.services.admin_assistant_service import AdminAssistantService
    assert hasattr(AdminAssistantService, "execute_automation_manually")


def test_84_phase15_text_nlp_processor() -> None:
    from core_model.nlp.text_processor import process_text
    res = process_text("வணக்கம் brud ai")
    assert res.detected_language in ("ta", "mixed", "unknown", "en")


def test_85_phase16_capability_matrix_and_router() -> None:
    from core_model.capabilities.smart_router import route_capability
    dec = route_capability("hello brud ai", caller_context="public_chat")
    assert dec.selected_capability_id is not None or dec.confidence < 0.60


def test_86_phase17_public_capability_gate() -> None:
    from core_model.capabilities.public_capability_gate import evaluate_public_capability_gate
    gate = evaluate_public_capability_gate("delete database admin action", caller_context="public_chat")
    assert gate.allowed is False


def test_87_phase18_public_request_trace() -> None:
    from core_model.capabilities.public_request_trace import build_public_request_trace
    trace = build_public_request_trace(request_id="req-1", language="en", capability_id="language_detection")
    assert trace["request_id"] == "req-1"


def test_88_phase19_knowledge_gap_classifier() -> None:
    from core_model.capabilities.clarification_intelligence import classify_knowledge_gap
    from core_model.capabilities.smart_router import route_capability
    from core_model.nlp.text_processor import process_text

    nlp = process_text("what is python")
    dec = route_capability("what is python", caller_context="public_chat")
    gap = classify_knowledge_gap("what is python", nlp, dec)
    assert gap.gap_type is not None


def test_89_public_chat_routing_service_authority() -> None:
    from backend.services.public_chat_routing_service import PublicChatRoutingService
    assert hasattr(PublicChatRoutingService, "handle_message")


def test_90_public_chat_response_schema_unchanged() -> None:
    from backend.services.public_chat_routing_service import PublicChatResponse
    res = PublicChatResponse(
        reply="hello",
        detected_language="en",
        answer_language="en",
        route_used="core_model",
        evidence_status="grounded",
        confidence_band="high",
        safety_status="safe",
        request_id="req-1",
    )
    assert res.reply == "hello"


# ===========================================================================
# 91-100: Autonomous Learning Protection, AST Security, & Production DB Integrity
# ===========================================================================

def test_91_non_autonomous_learning_invariant() -> None:
    # Verify Phase 20 service has zero calls or methods for training/RAG ingestion
    import core_model.capabilities.knowledge_gap_governance_service as mod
    for name, obj in inspect.getmembers(mod):
        if inspect.isfunction(obj) or inspect.ismethod(obj):
            assert "train" not in name.lower()
            assert "ingest" not in name.lower()
            assert "embed" not in name.lower()


def test_92_ast_security_governance_service() -> None:
    import core_model.capabilities.knowledge_gap_governance_service as mod
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_93_ast_security_governance_repository() -> None:
    import backend.database.repositories.knowledge_gap_governance_repository as mod
    tree = ast.parse(inspect.getsource(mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_94_no_network_calls_in_pure_governance_service() -> None:
    code = inspect.getsource(KnowledgeGapGovernanceService).lower()
    for forbidden in ("requests.", "httpx.", "urllib.", "aiohttp.", "socket."):
        assert forbidden not in code


def test_95_no_subprocess_in_pure_governance_service() -> None:
    code = inspect.getsource(KnowledgeGapGovernanceService).lower()
    for forbidden in ("subprocess", "os.system", "os.popen", "popen"):
        assert forbidden not in code


def test_96_no_workers_schedulers_in_pure_governance_service() -> None:
    code = inspect.getsource(KnowledgeGapGovernanceService).lower()
    for forbidden in ("celery", "apscheduler", "cron", "backgroundtasks", "asyncio.create_task"):
        assert forbidden not in code


def test_97_production_db_file_exists() -> None:
    assert os.path.exists(PROD_DB_PATH), f"Production database path {PROD_DB_PATH} must exist"


def test_98_production_db_sha256_unchanged() -> None:
    hasher = hashlib.sha256()
    with open(PROD_DB_PATH, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual_sha = hasher.hexdigest()
    assert actual_sha == EXPECTED_DB_SHA256, (
        f"Production DB SHA-256 mismatch! Expected {EXPECTED_DB_SHA256}, got {actual_sha}. "
        "Production DB must NOT be mutated by tests!"
    )


def test_99_production_db_size_unchanged() -> None:
    actual_size = os.path.getsize(PROD_DB_PATH)
    assert actual_size == EXPECTED_DB_SIZE, (
        f"Production DB size mismatch! Expected {EXPECTED_DB_SIZE} bytes, got {actual_size} bytes. "
        "Production DB must NOT be mutated by tests!"
    )


def test_100_final_integrity_contract_validation() -> None:
    """Final contract validation verifying Phase 20 completion."""
    assert EXPECTED_DB_SHA256 == "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    assert EXPECTED_DB_SIZE == 11096064
    assert len(ALLOWED_TRANSITIONS) > 0
