"""Phase 20 — Admin Knowledge Gap Governance Service & State Machine.

This pure domain service governs the review, candidate classification, and human approval
state machine for Knowledge Gap records captured from Phase 19 observations.

CRITICAL INVARIANTS:
- Knowledge Gap Observation != Training Data != RAG Knowledge != Model Weights.
- Candidate classification (RAG_CANDIDATE, DATASET_CANDIDATE) != Approval.
- Approval requires explicit authorized human decision.
- ZERO autonomous learning, zero background workers, zero external API calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from uuid import uuid4

from core_model.capabilities.knowledge_gap import (
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
    SEVERITY_CRITICAL,
    KnowledgeGap,
    sanitize_summary,
)

# ---------------------------------------------------------------------------
# Status Lifecycle Taxonomies
# ---------------------------------------------------------------------------
STATUS_NEW = "NEW"
STATUS_IN_REVIEW = "IN_REVIEW"
STATUS_CURATED = "CURATED"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_DEFERRED = "DEFERRED"

VALID_STATUSES: tuple[str, ...] = (
    STATUS_NEW,
    STATUS_IN_REVIEW,
    STATUS_CURATED,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_DEFERRED,
)

# Candidate Types
CANDIDATE_NONE = "NONE"
CANDIDATE_RAG = "RAG_CANDIDATE"
CANDIDATE_DATASET = "DATASET_CANDIDATE"

VALID_CANDIDATE_TYPES: tuple[str, ...] = (
    CANDIDATE_NONE,
    CANDIDATE_RAG,
    CANDIDATE_DATASET,
)

# Approval States
APPROVAL_NOT_REQUESTED = "NOT_REQUESTED"
APPROVAL_PENDING = "PENDING"
APPROVAL_APPROVED = "APPROVED"
APPROVAL_REJECTED = "REJECTED"

VALID_APPROVAL_STATES: tuple[str, ...] = (
    APPROVAL_NOT_REQUESTED,
    APPROVAL_PENDING,
    APPROVAL_APPROVED,
    APPROVAL_REJECTED,
)

# Permitted State Transitions Map
ALLOWED_TRANSITIONS: Mapping[str, tuple[str, ...]] = {
    STATUS_NEW: (STATUS_IN_REVIEW,),
    STATUS_IN_REVIEW: (STATUS_CURATED, STATUS_DEFERRED, STATUS_REJECTED),
    STATUS_CURATED: (STATUS_APPROVED, STATUS_REJECTED, STATUS_DEFERRED),
    STATUS_APPROVED: (),  # Terminal state
    STATUS_REJECTED: (),  # Terminal state
    STATUS_DEFERRED: (STATUS_IN_REVIEW,),  # Can return to review if policy permits
}


class InvalidStateTransitionError(ValueError):
    """Raised when an invalid status transition is attempted."""


class GovernanceSecurityError(PermissionError):
    """Raised when a security boundary rule is violated."""


@dataclass(frozen=True)
class KnowledgeGapRecord:
    """Immutable domain record for Phase 20 Admin Knowledge Gap Inbox."""

    record_id: str
    gap_id: str
    request_id: str
    detected_language: str
    language_confidence: float
    normalized_intent: str
    requested_capability_id: str | None
    selected_capability_id: str | None
    routing_confidence: float
    failure_classification: str
    gap_type: str
    severity: str
    clarification_required: bool
    clarification_question: str | None
    evidence_status: str
    source_stage: str
    safe_summary: str
    sanitized_metadata: Mapping[str, Any]
    status: str
    candidate_type: str
    approval_state: str
    created_at: str
    updated_at: str
    reviewed_at: str | None = None
    reviewed_by: str | None = None
    reviewer_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a clean, JSON-serializable dictionary representation."""
        return {
            "record_id": self.record_id,
            "gap_id": self.gap_id,
            "request_id": self.request_id,
            "detected_language": self.detected_language,
            "language_confidence": round(self.language_confidence, 4),
            "normalized_intent": self.normalized_intent,
            "requested_capability_id": self.requested_capability_id,
            "selected_capability_id": self.selected_capability_id,
            "routing_confidence": round(self.routing_confidence, 4),
            "failure_classification": self.failure_classification,
            "gap_type": self.gap_type,
            "severity": self.severity,
            "clarification_required": self.clarification_required,
            "clarification_question": self.clarification_question,
            "evidence_status": self.evidence_status,
            "source_stage": self.source_stage,
            "safe_summary": self.safe_summary,
            "sanitized_metadata": dict(self.sanitized_metadata),
            "status": self.status,
            "candidate_type": self.candidate_type,
            "approval_state": self.approval_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "reviewed_at": self.reviewed_at,
            "reviewed_by": self.reviewed_by,
            "reviewer_notes": self.reviewer_notes,
        }


def sanitize_metadata_dict(metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Sanitize metadata dictionary by removing secret keys and redacting text values."""
    forbidden_keys = {"password", "api_key", "bearer_token", "secret", "auth", "credentials"}
    sanitized: dict[str, Any] = {}
    for k, v in metadata.items():
        if any(fk in str(k).lower() for fk in forbidden_keys):
            continue
        if isinstance(v, str):
            sanitized[str(k)] = sanitize_summary(v)
        else:
            sanitized[str(k)] = v
    return sanitized


def create_record_from_gap(
    gap: KnowledgeGap,
    *,
    record_id: str | None = None,
    now_iso: str | None = None,
) -> KnowledgeGapRecord:
    """Construct an initial KnowledgeGapRecord in status NEW from a Phase 19 KnowledgeGap observation."""
    current_time = now_iso or datetime.now(UTC).isoformat()
    rec_id = record_id or f"rec-{uuid4()}"

    # Handle SECURITY_ADMIN_BOUNDARY invariants
    severity = gap.severity
    clarification_req = gap.clarification_required
    clarification_q = gap.clarification_question

    if gap.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY:
        severity = SEVERITY_CRITICAL
        clarification_req = False
        clarification_q = None

    return KnowledgeGapRecord(
        record_id=rec_id,
        gap_id=gap.gap_id,
        request_id=gap.request_id,
        detected_language=gap.detected_language,
        language_confidence=gap.language_confidence,
        normalized_intent=sanitize_summary(gap.normalized_intent),
        requested_capability_id=gap.requested_capability_id,
        selected_capability_id=gap.selected_capability_id,
        routing_confidence=gap.routing_confidence,
        failure_classification=gap.failure_classification,
        gap_type=gap.gap_type,
        severity=severity,
        clarification_required=clarification_req,
        clarification_question=clarification_q,
        evidence_status=gap.evidence_status,
        source_stage=gap.source_stage,
        safe_summary=sanitize_summary(gap.safe_summary),
        sanitized_metadata=sanitize_metadata_dict(gap.metadata),
        status=STATUS_NEW,
        candidate_type=CANDIDATE_NONE,
        approval_state=APPROVAL_NOT_REQUESTED,
        created_at=current_time,
        updated_at=current_time,
    )


class KnowledgeGapGovernanceService:
    """Pure domain state machine governing Phase 20 Knowledge Gap curation & human approval."""

    @staticmethod
    def validate_transition(current_status: str, target_status: str) -> None:
        """Validate if a status transition is permitted by the state machine."""
        if current_status not in VALID_STATUSES:
            raise InvalidStateTransitionError(f"Invalid current status {current_status!r}")
        if target_status not in VALID_STATUSES:
            raise InvalidStateTransitionError(f"Invalid target status {target_status!r}")
        allowed = ALLOWED_TRANSITIONS.get(current_status, ())
        if target_status not in allowed:
            raise InvalidStateTransitionError(
                f"Transition from {current_status!r} to {target_status!r} is not allowed. Allowed targets: {allowed}"
            )

    def start_review(
        self,
        record: KnowledgeGapRecord,
        *,
        reviewer_id: str,
        now_iso: str | None = None,
    ) -> KnowledgeGapRecord:
        """Transition record from NEW -> IN_REVIEW."""
        self.validate_transition(record.status, STATUS_IN_REVIEW)
        current_time = now_iso or datetime.now(UTC).isoformat()

        return KnowledgeGapRecord(
            **{
                **record.to_dict(),
                "status": STATUS_IN_REVIEW,
                "reviewed_by": reviewer_id,
                "reviewed_at": current_time,
                "updated_at": current_time,
            }
        )

    def classify_candidate(
        self,
        record: KnowledgeGapRecord,
        *,
        candidate_type: str,
        reviewer_id: str,
        reviewer_notes: str | None = None,
        now_iso: str | None = None,
    ) -> KnowledgeGapRecord:
        """Transition record from IN_REVIEW -> CURATED with a specific candidate type."""
        self.validate_transition(record.status, STATUS_CURATED)
        if candidate_type not in (CANDIDATE_RAG, CANDIDATE_DATASET):
            raise ValueError(
                f"Candidate classification must be RAG_CANDIDATE or DATASET_CANDIDATE, got {candidate_type!r}"
            )

        # SECURITY_ADMIN_BOUNDARY check
        if record.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY:
            raise GovernanceSecurityError(
                "SECURITY_ADMIN_BOUNDARY records cannot be classified as RAG/Dataset candidates for training"
            )

        current_time = now_iso or datetime.now(UTC).isoformat()
        notes = (record.reviewer_notes or "") + (f"\n{reviewer_notes}" if reviewer_notes else "")

        return KnowledgeGapRecord(
            **{
                **record.to_dict(),
                "status": STATUS_CURATED,
                "candidate_type": candidate_type,
                "approval_state": APPROVAL_PENDING,
                "reviewed_by": reviewer_id,
                "reviewed_at": current_time,
                "reviewer_notes": notes.strip() or None,
                "updated_at": current_time,
            }
        )

    def approve_candidate(
        self,
        record: KnowledgeGapRecord,
        *,
        approver_id: str,
        approval_notes: str | None = None,
        now_iso: str | None = None,
    ) -> KnowledgeGapRecord:
        """Transition record from CURATED -> APPROVED."""
        self.validate_transition(record.status, STATUS_APPROVED)
        if record.candidate_type not in (CANDIDATE_RAG, CANDIDATE_DATASET):
            raise InvalidStateTransitionError("Cannot approve a record with candidate_type NONE")

        if record.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY:
            raise GovernanceSecurityError("SECURITY_ADMIN_BOUNDARY records cannot be approved")

        current_time = now_iso or datetime.now(UTC).isoformat()
        notes = (record.reviewer_notes or "") + (f"\n[APPROVAL NOTE]: {approval_notes}" if approval_notes else "")

        return KnowledgeGapRecord(
            **{
                **record.to_dict(),
                "status": STATUS_APPROVED,
                "approval_state": APPROVAL_APPROVED,
                "reviewed_by": approver_id,
                "reviewed_at": current_time,
                "reviewer_notes": notes.strip() or None,
                "updated_at": current_time,
            }
        )

    def reject_candidate(
        self,
        record: KnowledgeGapRecord,
        *,
        reviewer_id: str,
        rejection_reason: str | None = None,
        now_iso: str | None = None,
    ) -> KnowledgeGapRecord:
        """Transition record from IN_REVIEW or CURATED -> REJECTED."""
        self.validate_transition(record.status, STATUS_REJECTED)
        current_time = now_iso or datetime.now(UTC).isoformat()
        notes = (record.reviewer_notes or "") + (f"\n[REJECTION REASON]: {rejection_reason}" if rejection_reason else "")

        return KnowledgeGapRecord(
            **{
                **record.to_dict(),
                "status": STATUS_REJECTED,
                "approval_state": APPROVAL_REJECTED if record.candidate_type != CANDIDATE_NONE else APPROVAL_NOT_REQUESTED,
                "reviewed_by": reviewer_id,
                "reviewed_at": current_time,
                "reviewer_notes": notes.strip() or None,
                "updated_at": current_time,
            }
        )

    def defer_candidate(
        self,
        record: KnowledgeGapRecord,
        *,
        reviewer_id: str,
        deferral_reason: str | None = None,
        now_iso: str | None = None,
    ) -> KnowledgeGapRecord:
        """Transition record from IN_REVIEW or CURATED -> DEFERRED."""
        self.validate_transition(record.status, STATUS_DEFERRED)
        current_time = now_iso or datetime.now(UTC).isoformat()
        notes = (record.reviewer_notes or "") + (f"\n[DEFERRAL REASON]: {deferral_reason}" if deferral_reason else "")

        return KnowledgeGapRecord(
            **{
                **record.to_dict(),
                "status": STATUS_DEFERRED,
                "reviewed_by": reviewer_id,
                "reviewed_at": current_time,
                "reviewer_notes": notes.strip() or None,
                "updated_at": current_time,
            }
        )


__all__ = [
    "ALLOWED_TRANSITIONS",
    "APPROVAL_APPROVED",
    "APPROVAL_NOT_REQUESTED",
    "APPROVAL_PENDING",
    "APPROVAL_REJECTED",
    "CANDIDATE_DATASET",
    "CANDIDATE_NONE",
    "CANDIDATE_RAG",
    "GovernanceSecurityError",
    "InvalidStateTransitionError",
    "KnowledgeGapGovernanceService",
    "KnowledgeGapRecord",
    "STATUS_APPROVED",
    "STATUS_CURATED",
    "STATUS_DEFERRED",
    "STATUS_IN_REVIEW",
    "STATUS_NEW",
    "STATUS_REJECTED",
    "VALID_APPROVAL_STATES",
    "VALID_CANDIDATE_TYPES",
    "VALID_STATUSES",
    "create_record_from_gap",
]
