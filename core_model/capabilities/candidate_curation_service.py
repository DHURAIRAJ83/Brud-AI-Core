"""Phase 21 — Human-Approved RAG & Dataset Candidate Curation Domain Service.

This pure domain service governs the candidate provenance, quality validation,
duplicate & conflict detection, and staging state machine for Phase 20 governance-approved
Knowledge Gap candidates.

CRITICAL INVARIANTS:
  - Knowledge Gap != Candidate != Approved Candidate != Staged Artifact != Production RAG Data != Training Dataset != Model Weights.
  - Phase 20 explicit approval (status == APPROVED and approval_state == APPROVED) is MANDATORY before staging.
  - Candidate classification alone (candidate_type == RAG_CANDIDATE / DATASET_CANDIDATE) does NOT authorize Phase 21 staging.
  - Quality Validation PASS != Staging Approval.
  - SECURITY_ADMIN_BOUNDARY records cannot be converted into staged candidates or approved.
  - ZERO autonomous learning, zero background workers, zero external API calls.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from uuid import uuid4

from core_model.capabilities.knowledge_gap import (
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
    SEVERITY_CRITICAL,
    sanitize_summary,
)
from core_model.capabilities.knowledge_gap_governance_service import (
    APPROVAL_APPROVED,
    CANDIDATE_DATASET,
    CANDIDATE_RAG,
    STATUS_APPROVED,
    GovernanceSecurityError,
    KnowledgeGapRecord,
    sanitize_metadata_dict,
)

# ---------------------------------------------------------------------------
# Phase 21 Staging Status Constants
# ---------------------------------------------------------------------------
STAGING_STATUS_DRAFT = "DRAFT"
STAGING_STATUS_VALIDATED = "VALIDATED"
STAGING_STATUS_PENDING_REVIEW = "PENDING_REVIEW"
STAGING_STATUS_APPROVED = "APPROVED"
STAGING_STATUS_REJECTED = "REJECTED"
STAGING_STATUS_DEFERRED = "DEFERRED"

# Terminal Ingestion/Export Readiness Statuses
RAG_STATUS_READY_FOR_INGESTION = "READY_FOR_INGESTION"
DATASET_STATUS_READY_FOR_EXPORT = "READY_FOR_EXPORT"

VALID_STAGING_STATUSES: tuple[str, ...] = (
    STAGING_STATUS_DRAFT,
    STAGING_STATUS_VALIDATED,
    STAGING_STATUS_PENDING_REVIEW,
    STAGING_STATUS_APPROVED,
    STAGING_STATUS_REJECTED,
    STAGING_STATUS_DEFERRED,
    RAG_STATUS_READY_FOR_INGESTION,
    DATASET_STATUS_READY_FOR_EXPORT,
)

# Validation Status Constants
VALIDATION_PASS = "PASS"
VALIDATION_FAIL = "FAIL"
VALIDATION_NEEDS_REVISION = "NEEDS_REVISION"

# Duplicate Status Constants
DUPLICATE_UNIQUE = "UNIQUE"
DUPLICATE_EXACT = "EXACT_DUPLICATE"
DUPLICATE_PROBABLE = "PROBABLE_DUPLICATE"

# Conflict Status Constants
CONFLICT_NONE = "NO_CONFLICT"
CONFLICT_CONFLICTING = "CONFLICTING"

# Staging State Transition Maps
RAG_ALLOWED_TRANSITIONS: Mapping[str, tuple[str, ...]] = {
    STAGING_STATUS_DRAFT: (STAGING_STATUS_VALIDATED, STAGING_STATUS_REJECTED),
    STAGING_STATUS_VALIDATED: (STAGING_STATUS_PENDING_REVIEW, STAGING_STATUS_REJECTED, STAGING_STATUS_DEFERRED),
    STAGING_STATUS_PENDING_REVIEW: (STAGING_STATUS_APPROVED, STAGING_STATUS_REJECTED, STAGING_STATUS_DEFERRED),
    STAGING_STATUS_APPROVED: (RAG_STATUS_READY_FOR_INGESTION,),
    RAG_STATUS_READY_FOR_INGESTION: (),  # Terminal state
    STAGING_STATUS_REJECTED: (),  # Terminal state
    STAGING_STATUS_DEFERRED: (STAGING_STATUS_PENDING_REVIEW,),  # Can return to review
}

DATASET_ALLOWED_TRANSITIONS: Mapping[str, tuple[str, ...]] = {
    STAGING_STATUS_DRAFT: (STAGING_STATUS_VALIDATED, STAGING_STATUS_REJECTED),
    STAGING_STATUS_VALIDATED: (STAGING_STATUS_PENDING_REVIEW, STAGING_STATUS_REJECTED, STAGING_STATUS_DEFERRED),
    STAGING_STATUS_PENDING_REVIEW: (STAGING_STATUS_APPROVED, STAGING_STATUS_REJECTED, STAGING_STATUS_DEFERRED),
    STAGING_STATUS_APPROVED: (DATASET_STATUS_READY_FOR_EXPORT,),
    DATASET_STATUS_READY_FOR_EXPORT: (),  # Terminal state
    STAGING_STATUS_REJECTED: (),  # Terminal state
    STAGING_STATUS_DEFERRED: (STAGING_STATUS_PENDING_REVIEW,),  # Can return to review
}


class InvalidStagingTransitionError(ValueError):
    """Raised when an invalid candidate staging status transition is attempted."""


class CandidateProvenanceError(ValueError):
    """Raised when provenance validation fails or source record is not approved."""


# ---------------------------------------------------------------------------
# Immutable Provenance & Staging Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CandidateProvenance:
    """Immutable provenance record tracing candidate origin back to Phase 19/20."""

    provenance_id: str
    source_record_id: str
    source_gap_id: str
    source_request_id: str
    source_gap_type: str
    source_severity: str
    source_summary: str
    candidate_type: str
    approved_by: str
    approved_at: str
    source_stage: str = "routing"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "provenance_id": self.provenance_id,
            "source_record_id": self.source_record_id,
            "source_gap_id": self.source_gap_id,
            "source_request_id": self.source_request_id,
            "source_gap_type": self.source_gap_type,
            "source_severity": self.source_severity,
            "source_summary": self.source_summary,
            "candidate_type": self.candidate_type,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "source_stage": self.source_stage,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class CandidateValidationResult:
    """Immutable result of candidate quality validation."""

    is_valid: bool
    validation_status: str
    issue_count: int
    issues: tuple[str, ...]
    warnings: tuple[str, ...]
    metadata: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "validation_status": self.validation_status,
            "issue_count": self.issue_count,
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CandidateDuplicateConflictResult:
    """Immutable result of candidate duplicate & conflict analysis."""

    duplicate_status: str
    conflict_status: str
    matched_candidate_id: str | None = None
    matched_content_hash: str | None = None
    conflict_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "duplicate_status": self.duplicate_status,
            "conflict_status": self.conflict_status,
            "matched_candidate_id": self.matched_candidate_id,
            "matched_content_hash": self.matched_content_hash,
            "conflict_reason": self.conflict_reason,
        }


@dataclass(frozen=True)
class RAGCandidateStagingRecord:
    """Immutable domain record for a staged RAG candidate."""

    candidate_id: str
    provenance: CandidateProvenance
    title: str
    content: str
    content_hash: str
    provenance_hash: str
    candidate_version: str
    validation_status: str
    duplicate_status: str
    conflict_status: str
    status: str
    created_at: str
    updated_at: str
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    reviewer_notes: str | None = None
    sanitized_metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "provenance": self.provenance.to_dict(),
            "title": self.title,
            "content": self.content,
            "content_hash": self.content_hash,
            "provenance_hash": self.provenance_hash,
            "candidate_version": self.candidate_version,
            "validation_status": self.validation_status,
            "duplicate_status": self.duplicate_status,
            "conflict_status": self.conflict_status,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reviewed_at": self.reviewed_at,
            "reviewed_by": self.reviewed_by,
            "reviewer_notes": self.reviewer_notes,
            "sanitized_metadata": dict(self.sanitized_metadata),
        }


@dataclass(frozen=True)
class DatasetCandidateStagingRecord:
    """Immutable domain record for a staged Dataset candidate."""

    candidate_id: str
    provenance: CandidateProvenance
    input_context: str
    proposed_output: str
    language: str
    domain_topic: str
    content_hash: str
    provenance_hash: str
    candidate_version: str
    validation_status: str
    duplicate_status: str
    conflict_status: str
    status: str
    created_at: str
    updated_at: str
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    reviewer_notes: str | None = None
    sanitized_metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "provenance": self.provenance.to_dict(),
            "input_context": self.input_context,
            "proposed_output": self.proposed_output,
            "language": self.language,
            "domain_topic": self.domain_topic,
            "content_hash": self.content_hash,
            "provenance_hash": self.provenance_hash,
            "candidate_version": self.candidate_version,
            "validation_status": self.validation_status,
            "duplicate_status": self.duplicate_status,
            "conflict_status": self.conflict_status,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reviewed_at": self.reviewed_at,
            "reviewed_by": self.reviewed_by,
            "reviewer_notes": self.reviewer_notes,
            "sanitized_metadata": dict(self.sanitized_metadata),
        }


# ---------------------------------------------------------------------------
# Pure Helper Functions (Hashing, Validation, Sanitization, Matching)
# ---------------------------------------------------------------------------

def compute_canonical_content_hash(text: str) -> str:
    """Deterministic SHA-256 hash of normalized text."""
    normalized = text.strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_provenance_hash(prov: CandidateProvenance) -> str:
    """Deterministic SHA-256 hash of provenance lineage key identifiers."""
    raw = f"{prov.source_gap_id}:{prov.source_record_id}:{prov.source_request_id}:{prov.candidate_type}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_candidate_quality(
    *,
    provenance: CandidateProvenance,
    title_or_input: str,
    content_or_output: str,
    sanitized_metadata: Mapping[str, Any] | None = None,
    min_length: int = 3,
    max_length: int = 50000,
) -> CandidateValidationResult:
    """Deterministic, non-LLM quality validation of candidate parameters."""
    issues: list[str] = []
    warnings: list[str] = []

    # 1. Provenance Checks
    if not provenance.provenance_id:
        issues.append("missing_provenance_id")
    if not provenance.source_record_id or not provenance.source_gap_id:
        issues.append("missing_source_identifiers")
    if not provenance.approved_by or not provenance.approved_at:
        issues.append("missing_approval_metadata")

    # 2. Content Checks
    title_clean = title_or_input.strip()
    content_clean = content_or_output.strip()

    if not title_clean:
        issues.append("empty_title_or_input")
    if not content_clean:
        issues.append("empty_content_or_output")

    if len(content_clean) < min_length:
        issues.append(f"content_too_short:less_than_{min_length}_chars")
    if len(content_clean) > max_length:
        issues.append(f"content_too_long:exceeds_{max_length}_chars")

    # 3. Secret Sanitization Checks
    secret_terms = ("sk-", "bearer ", "password=", "secret=", "api_key=")
    if any(st in title_clean.lower() for st in secret_terms) or any(st in content_clean.lower() for st in secret_terms):
        issues.append("unredacted_secret_detected_in_content")

    # 4. Metadata Checks
    if sanitized_metadata:
        for k in sanitized_metadata:
            if any(fk in str(k).lower() for fk in ("password", "api_key", "bearer_token", "secret", "auth", "credentials")):
                issues.append(f"forbidden_metadata_key:{k}")

    # Determine status
    if issues:
        status = VALIDATION_FAIL
        is_valid = False
    elif warnings:
        status = VALIDATION_NEEDS_REVISION
        is_valid = True
    else:
        status = VALIDATION_PASS
        is_valid = True

    return CandidateValidationResult(
        is_valid=is_valid,
        validation_status=status,
        issue_count=len(issues),
        issues=tuple(issues),
        warnings=tuple(warnings),
        metadata={"validated_at": datetime.now(UTC).isoformat()},
    )


def detect_candidate_duplicates_and_conflicts(
    new_content_hash: str,
    new_provenance_hash: str,
    existing_candidates: Sequence[RAGCandidateStagingRecord | DatasetCandidateStagingRecord],
) -> CandidateDuplicateConflictResult:
    """Deterministic duplicate & conflict detection against existing staged records."""
    matched_id: str | None = None
    matched_hash: str | None = None
    dup_status = DUPLICATE_UNIQUE
    conflict_status = CONFLICT_NONE
    conflict_reason: str | None = None

    for existing in existing_candidates:
        # Check exact content duplicate
        if existing.content_hash == new_content_hash:
            dup_status = DUPLICATE_EXACT
            matched_id = existing.candidate_id
            matched_hash = existing.content_hash
            break

        # Check provenance match with conflicting content
        if existing.provenance_hash == new_provenance_hash and existing.content_hash != new_content_hash:
            conflict_status = CONFLICT_CONFLICTING
            matched_id = existing.candidate_id
            matched_hash = existing.content_hash
            conflict_reason = f"Same provenance identity as candidate {existing.candidate_id} but different content"
            break

    return CandidateDuplicateConflictResult(
        duplicate_status=dup_status,
        conflict_status=conflict_status,
        matched_candidate_id=matched_id,
        matched_content_hash=matched_hash,
        conflict_reason=conflict_reason,
    )


# ---------------------------------------------------------------------------
# Staging Factory Functions
# ---------------------------------------------------------------------------

def stage_rag_candidate(
    record: KnowledgeGapRecord,
    *,
    title: str,
    content: str,
    staged_by: str,
    existing_records: Sequence[RAGCandidateStagingRecord] = (),
    candidate_id: str | None = None,
    candidate_version: str = "1.0.0",
    now_iso: str | None = None,
) -> RAGCandidateStagingRecord:
    """Stage a Phase 20 APPROVED Knowledge Gap record as a RAG Candidate."""
    # Enforce Security Boundary Invariant
    if record.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY:
        raise GovernanceSecurityError(
            f"Record {record.record_id} is a SECURITY_ADMIN_BOUNDARY and CANNOT be staged as a RAG candidate."
        )

    # Enforce Phase 20 Approval Invariant
    if record.status != STATUS_APPROVED or record.approval_state != APPROVAL_APPROVED:
        raise CandidateProvenanceError(
            f"Record {record.record_id} is not approved in Phase 20 (status={record.status}, approval_state={record.approval_state}). "
            "Phase 20 explicit approval is mandatory before Phase 21 staging."
        )

    # Enforce Candidate Type Invariant
    if record.candidate_type != CANDIDATE_RAG:
        raise CandidateProvenanceError(
            f"Record {record.record_id} candidate_type is '{record.candidate_type}', expected '{CANDIDATE_RAG}'."
        )

    current_time = now_iso or datetime.now(UTC).isoformat()
    cid = candidate_id or f"rag-cand-{uuid4()}"

    # Build Provenance
    prov = CandidateProvenance(
        provenance_id=f"prov-{uuid4()}",
        source_record_id=record.record_id,
        source_gap_id=record.gap_id,
        source_request_id=record.request_id,
        source_gap_type=record.gap_type,
        source_severity=record.severity,
        source_summary=record.safe_summary,
        candidate_type=CANDIDATE_RAG,
        approved_by=record.reviewed_by or staged_by,
        approved_at=record.reviewed_at or current_time,
        source_stage=record.source_stage,
        created_at=current_time,
    )

    # Sanitization
    clean_title = sanitize_summary(title)
    clean_content = sanitize_summary(content)
    clean_metadata = sanitize_metadata_dict(record.sanitized_metadata)

    # Hashes
    c_hash = compute_canonical_content_hash(clean_content)
    p_hash = compute_provenance_hash(prov)

    # Validation
    val_res = validate_candidate_quality(
        provenance=prov,
        title_or_input=clean_title,
        content_or_output=clean_content,
        sanitized_metadata=clean_metadata,
    )

    # Duplicate / Conflict Detection
    dup_res = detect_candidate_duplicates_and_conflicts(c_hash, p_hash, existing_records)

    # Initial Staging Status: VALIDATED if valid, else DRAFT
    initial_status = STAGING_STATUS_VALIDATED if val_res.is_valid else STAGING_STATUS_DRAFT

    return RAGCandidateStagingRecord(
        candidate_id=cid,
        provenance=prov,
        title=clean_title,
        content=clean_content,
        content_hash=c_hash,
        provenance_hash=p_hash,
        candidate_version=candidate_version,
        validation_status=val_res.validation_status,
        duplicate_status=dup_res.duplicate_status,
        conflict_status=dup_res.conflict_status,
        status=initial_status,
        created_at=current_time,
        updated_at=current_time,
        sanitized_metadata=clean_metadata,
    )


def stage_dataset_candidate(
    record: KnowledgeGapRecord,
    *,
    input_context: str,
    proposed_output: str,
    language: str,
    domain_topic: str,
    staged_by: str,
    existing_records: Sequence[DatasetCandidateStagingRecord] = (),
    candidate_id: str | None = None,
    candidate_version: str = "1.0.0",
    now_iso: str | None = None,
) -> DatasetCandidateStagingRecord:
    """Stage a Phase 20 APPROVED Knowledge Gap record as a Dataset Candidate."""
    # Enforce Security Boundary Invariant
    if record.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY:
        raise GovernanceSecurityError(
            f"Record {record.record_id} is a SECURITY_ADMIN_BOUNDARY and CANNOT be staged as a Dataset candidate."
        )

    # Enforce Phase 20 Approval Invariant
    if record.status != STATUS_APPROVED or record.approval_state != APPROVAL_APPROVED:
        raise CandidateProvenanceError(
            f"Record {record.record_id} is not approved in Phase 20 (status={record.status}, approval_state={record.approval_state}). "
            "Phase 20 explicit approval is mandatory before Phase 21 staging."
        )

    # Enforce Candidate Type Invariant
    if record.candidate_type != CANDIDATE_DATASET:
        raise CandidateProvenanceError(
            f"Record {record.record_id} candidate_type is '{record.candidate_type}', expected '{CANDIDATE_DATASET}'."
        )

    current_time = now_iso or datetime.now(UTC).isoformat()
    cid = candidate_id or f"ds-cand-{uuid4()}"

    # Build Provenance
    prov = CandidateProvenance(
        provenance_id=f"prov-{uuid4()}",
        source_record_id=record.record_id,
        source_gap_id=record.gap_id,
        source_request_id=record.request_id,
        source_gap_type=record.gap_type,
        source_severity=record.severity,
        source_summary=record.safe_summary,
        candidate_type=CANDIDATE_DATASET,
        approved_by=record.reviewed_by or staged_by,
        approved_at=record.reviewed_at or current_time,
        source_stage=record.source_stage,
        created_at=current_time,
    )

    # Sanitization
    clean_input = sanitize_summary(input_context)
    clean_output = sanitize_summary(proposed_output)
    clean_metadata = sanitize_metadata_dict(record.sanitized_metadata)

    # Hashes
    c_hash = compute_canonical_content_hash(f"{clean_input}:{clean_output}")
    p_hash = compute_provenance_hash(prov)

    # Validation
    val_res = validate_candidate_quality(
        provenance=prov,
        title_or_input=clean_input,
        content_or_output=clean_output,
        sanitized_metadata=clean_metadata,
    )

    # Duplicate / Conflict Detection
    dup_res = detect_candidate_duplicates_and_conflicts(c_hash, p_hash, existing_records)

    # Initial Staging Status: VALIDATED if valid, else DRAFT
    initial_status = STAGING_STATUS_VALIDATED if val_res.is_valid else STAGING_STATUS_DRAFT

    return DatasetCandidateStagingRecord(
        candidate_id=cid,
        provenance=prov,
        input_context=clean_input,
        proposed_output=clean_output,
        language=language or record.detected_language,
        domain_topic=domain_topic or record.gap_type,
        content_hash=c_hash,
        provenance_hash=p_hash,
        candidate_version=candidate_version,
        validation_status=val_res.validation_status,
        duplicate_status=dup_res.duplicate_status,
        conflict_status=dup_res.conflict_status,
        status=initial_status,
        created_at=current_time,
        updated_at=current_time,
        sanitized_metadata=clean_metadata,
    )


# ---------------------------------------------------------------------------
# CandidateCurationService — Pure State Machine
# ---------------------------------------------------------------------------

class CandidateCurationService:
    """Pure domain service managing candidate staging state transitions."""

    def start_review(
        self,
        candidate: RAGCandidateStagingRecord | DatasetCandidateStagingRecord,
        *,
        reviewer_id: str,
        now_iso: str | None = None,
    ) -> RAGCandidateStagingRecord | DatasetCandidateStagingRecord:
        """Transition staged candidate from VALIDATED or DEFERRED -> PENDING_REVIEW."""
        current_status = candidate.status
        allowed = (STAGING_STATUS_VALIDATED, STAGING_STATUS_DEFERRED, STAGING_STATUS_DRAFT)

        if current_status not in allowed:
            raise InvalidStagingTransitionError(
                f"Cannot start review on candidate {candidate.candidate_id} from status '{current_status}'. Allowed: {allowed}."
            )

        current_time = now_iso or datetime.now(UTC).isoformat()
        kwargs = {
            "status": STAGING_STATUS_PENDING_REVIEW,
            "reviewed_by": reviewer_id,
            "reviewed_at": current_time,
            "updated_at": current_time,
        }

        if isinstance(candidate, RAGCandidateStagingRecord):
            return RAGCandidateStagingRecord(**{**candidate.__dict__, **kwargs})
        else:
            return DatasetCandidateStagingRecord(**{**candidate.__dict__, **kwargs})

    def approve_staging(
        self,
        candidate: RAGCandidateStagingRecord | DatasetCandidateStagingRecord,
        *,
        approver_id: str,
        approval_notes: str | None = None,
        now_iso: str | None = None,
    ) -> RAGCandidateStagingRecord | DatasetCandidateStagingRecord:
        """Approve staged candidate, advancing status to APPROVED (READY_FOR_INGESTION / READY_FOR_EXPORT)."""
        current_status = candidate.status
        if current_status != STAGING_STATUS_PENDING_REVIEW:
            raise InvalidStagingTransitionError(
                f"Cannot approve candidate {candidate.candidate_id} from status '{current_status}'. Must be in PENDING_REVIEW."
            )

        current_time = now_iso or datetime.now(UTC).isoformat()
        combined_notes = (
            f"{candidate.reviewer_notes}\n[Approval Note by {approver_id}]: {approval_notes}".strip()
            if candidate.reviewer_notes and approval_notes
            else (approval_notes or candidate.reviewer_notes)
        )

        if isinstance(candidate, RAGCandidateStagingRecord):
            # Advances to READY_FOR_INGESTION for future Phase 22
            return RAGCandidateStagingRecord(
                **{
                    **candidate.__dict__,
                    "status": RAG_STATUS_READY_FOR_INGESTION,
                    "reviewed_by": approver_id,
                    "reviewed_at": current_time,
                    "reviewer_notes": combined_notes,
                    "updated_at": current_time,
                }
            )
        else:
            # Advances to READY_FOR_EXPORT for future Phase 22
            return DatasetCandidateStagingRecord(
                **{
                    **candidate.__dict__,
                    "status": DATASET_STATUS_READY_FOR_EXPORT,
                    "reviewed_by": approver_id,
                    "reviewed_at": current_time,
                    "reviewer_notes": combined_notes,
                    "updated_at": current_time,
                }
            )

    def reject_staging(
        self,
        candidate: RAGCandidateStagingRecord | DatasetCandidateStagingRecord,
        *,
        reviewer_id: str,
        rejection_reason: str | None = None,
        now_iso: str | None = None,
    ) -> RAGCandidateStagingRecord | DatasetCandidateStagingRecord:
        """Reject staged candidate."""
        current_status = candidate.status
        allowed = (STAGING_STATUS_DRAFT, STAGING_STATUS_VALIDATED, STAGING_STATUS_PENDING_REVIEW)
        if current_status not in allowed:
            raise InvalidStagingTransitionError(
                f"Cannot reject candidate {candidate.candidate_id} from status '{current_status}'. Allowed: {allowed}."
            )

        current_time = now_iso or datetime.now(UTC).isoformat()
        combined_notes = (
            f"{candidate.reviewer_notes}\n[Rejection Reason by {reviewer_id}]: {rejection_reason}".strip()
            if candidate.reviewer_notes and rejection_reason
            else (rejection_reason or candidate.reviewer_notes)
        )

        kwargs = {
            "status": STAGING_STATUS_REJECTED,
            "reviewed_by": reviewer_id,
            "reviewed_at": current_time,
            "reviewer_notes": combined_notes,
            "updated_at": current_time,
        }

        if isinstance(candidate, RAGCandidateStagingRecord):
            return RAGCandidateStagingRecord(**{**candidate.__dict__, **kwargs})
        else:
            return DatasetCandidateStagingRecord(**{**candidate.__dict__, **kwargs})

    def defer_staging(
        self,
        candidate: RAGCandidateStagingRecord | DatasetCandidateStagingRecord,
        *,
        reviewer_id: str,
        deferral_reason: str | None = None,
        now_iso: str | None = None,
    ) -> RAGCandidateStagingRecord | DatasetCandidateStagingRecord:
        """Defer staged candidate."""
        current_status = candidate.status
        allowed = (STAGING_STATUS_VALIDATED, STAGING_STATUS_PENDING_REVIEW)
        if current_status not in allowed:
            raise InvalidStagingTransitionError(
                f"Cannot defer candidate {candidate.candidate_id} from status '{current_status}'. Allowed: {allowed}."
            )

        current_time = now_iso or datetime.now(UTC).isoformat()
        combined_notes = (
            f"{candidate.reviewer_notes}\n[Deferral Reason by {reviewer_id}]: {deferral_reason}".strip()
            if candidate.reviewer_notes and deferral_reason
            else (deferral_reason or candidate.reviewer_notes)
        )

        kwargs = {
            "status": STAGING_STATUS_DEFERRED,
            "reviewed_by": reviewer_id,
            "reviewed_at": current_time,
            "reviewer_notes": combined_notes,
            "updated_at": current_time,
        }

        if isinstance(candidate, RAGCandidateStagingRecord):
            return RAGCandidateStagingRecord(**{**candidate.__dict__, **kwargs})
        else:
            return DatasetCandidateStagingRecord(**{**candidate.__dict__, **kwargs})
