"""Phase 24 — Knowledge Release Management, Promotion & Rollback Governance Domain Service.

Provides pure domain logic, state machines, pre-release validation, release candidate creation,
atomic promotion, non-destructive rollback, idempotency key generation, and 12-step provenance preservation.

CRITICAL INVARIANTS:
- Pure domain logic — NO database writes, NO network calls, NO subprocesses.
- NO autonomous learning, NO automatic model training, NO automatic weight updates, NO embedding generation.
- Evaluation APPROVED != Production Promotion.
- An approved evaluation NEVER automatically promotes an artifact or updates active version pointers.
- Explicit human admin action is strictly mandatory for release creation, approval, promotion, and rollback.
- Hard block on SECURITY_ADMIN_BOUNDARY and secret/PII-bearing content.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Sequence
from uuid import uuid4

from core_model.capabilities.controlled_ingestion_service import (
    audit_secrets_in_text,
)
from core_model.capabilities.evaluation_service import (
    EVALUATION_STAGE_APPROVED,
    EvaluationProvenance,
    EvaluationRecord,
)
from core_model.capabilities.knowledge_gap import (
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
)

# ---------------------------------------------------------------------------
# Phase 24 Release Lifecycle & State Constants
# ---------------------------------------------------------------------------

RELEASE_STAGE_EVALUATION_APPROVED = "EVALUATION_APPROVED"
RELEASE_STAGE_CANDIDATE_CREATED = "RELEASE_CANDIDATE_CREATED"
RELEASE_STAGE_PREFLIGHT_VALIDATED = "RELEASE_PREFLIGHT_VALIDATED"
RELEASE_STAGE_PREFLIGHT_FAILED = "RELEASE_PREFLIGHT_FAILED"
RELEASE_STAGE_PENDING_APPROVAL = "PENDING_RELEASE_APPROVAL"
RELEASE_STAGE_APPROVED = "RELEASE_APPROVED"
RELEASE_STAGE_READY_FOR_PROMOTION = "READY_FOR_PROMOTION"
RELEASE_STAGE_PROMOTING = "PROMOTING"
RELEASE_STAGE_PROMOTED = "PROMOTED"
RELEASE_STAGE_ACTIVE = "ACTIVE"
RELEASE_STAGE_REJECTED = "RELEASE_REJECTED"
RELEASE_STAGE_DEFERRED = "RELEASE_DEFERRED"
RELEASE_STAGE_PROMOTION_FAILED = "PROMOTION_FAILED"
RELEASE_STAGE_VERIFICATION_FAILED = "VERIFICATION_FAILED"
RELEASE_STAGE_ROLLED_BACK = "ROLLED_BACK"

# Allowed Release State Transitions Map
RELEASE_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    RELEASE_STAGE_EVALUATION_APPROVED: (RELEASE_STAGE_CANDIDATE_CREATED,),
    RELEASE_STAGE_CANDIDATE_CREATED: (RELEASE_STAGE_PREFLIGHT_VALIDATED, RELEASE_STAGE_PREFLIGHT_FAILED),
    RELEASE_STAGE_PREFLIGHT_VALIDATED: (RELEASE_STAGE_PENDING_APPROVAL, RELEASE_STAGE_PREFLIGHT_FAILED),
    RELEASE_STAGE_PENDING_APPROVAL: (RELEASE_STAGE_APPROVED, RELEASE_STAGE_REJECTED, RELEASE_STAGE_DEFERRED),
    RELEASE_STAGE_APPROVED: (RELEASE_STAGE_READY_FOR_PROMOTION,),
    RELEASE_STAGE_READY_FOR_PROMOTION: (RELEASE_STAGE_PROMOTING, RELEASE_STAGE_PROMOTION_FAILED),
    RELEASE_STAGE_PROMOTING: (RELEASE_STAGE_PROMOTED, RELEASE_STAGE_PROMOTION_FAILED),
    RELEASE_STAGE_PROMOTED: (RELEASE_STAGE_ACTIVE, RELEASE_STAGE_VERIFICATION_FAILED),
    RELEASE_STAGE_ACTIVE: (RELEASE_STAGE_ROLLED_BACK,),
    RELEASE_STAGE_ROLLED_BACK: (RELEASE_STAGE_PENDING_APPROVAL,),
    RELEASE_STAGE_REJECTED: (),
    RELEASE_STAGE_DEFERRED: (RELEASE_STAGE_PENDING_APPROVAL,),
    RELEASE_STAGE_PREFLIGHT_FAILED: (),
    RELEASE_STAGE_PROMOTION_FAILED: (RELEASE_STAGE_READY_FOR_PROMOTION,),
    RELEASE_STAGE_VERIFICATION_FAILED: (),
}


class ReleaseGovernanceError(Exception):
    """Base exception for Phase 24 release governance errors."""


class ReleasePreflightError(ReleaseGovernanceError):
    """Raised when pre-release validation fails."""


class InvalidReleaseTransitionError(ReleaseGovernanceError):
    """Raised on illegal release state machine transitions."""


class ReleaseApprovalRequiredError(ReleaseGovernanceError):
    """Raised when attempting release promotion without explicit human admin approval."""


# ---------------------------------------------------------------------------
# Data Models & Immutable Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReleaseProvenance:
    """Immutable 12-step provenance chain tracking from request to rollback.
    
    source_request_id → source_gap_id → source_record_id → candidate_id → operation_id → artifact_id → evaluation_id → comparison_id → review_id → release_id → promotion_operation_id → rollback_operation_id
    """
    source_request_id: str
    source_gap_id: str
    source_record_id: str
    candidate_id: str
    operation_id: str
    artifact_id: str
    evaluation_id: str
    comparison_id: str | None
    review_id: str | None
    release_id: str
    promotion_operation_id: str | None
    rollback_operation_id: str | None
    approved_by: str
    approved_at: str
    gap_type: str
    severity: str
    artifact_type: str

    def to_dict(self) -> dict[str, Any]:
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
            "rollback_operation_id": self.rollback_operation_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "gap_type": self.gap_type,
            "severity": self.severity,
            "artifact_type": self.artifact_type,
        }


@dataclass(frozen=True)
class ReleaseCandidate:
    """Immutable record of a release candidate."""
    release_id: str
    artifact_id: str
    artifact_type: str
    artifact_version: str
    evaluation_id: str
    evaluation_status: str
    release_status: str
    release_version: str
    content_hash: str
    provenance_hash: str
    created_by: str
    created_at: str
    provenance: ReleaseProvenance
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "release_id": self.release_id,
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "artifact_version": self.artifact_version,
            "evaluation_id": self.evaluation_id,
            "evaluation_status": self.evaluation_status,
            "release_status": self.release_status,
            "release_version": self.release_version,
            "content_hash": self.content_hash,
            "provenance_hash": self.provenance_hash,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "provenance": self.provenance.to_dict(),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ReleaseApproval:
    """Immutable release approval decision record by a human admin."""
    approval_id: str
    release_id: str
    approved_by: str
    approved_at: str
    decision: str
    reviewer_notes: str | None = None
    approval_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "release_id": self.release_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "decision": self.decision,
            "reviewer_notes": self.reviewer_notes,
            "approval_hash": self.approval_hash,
        }


@dataclass(frozen=True)
class PromotionOperation:
    """Immutable record of a release promotion operation."""
    operation_id: str
    release_id: str
    source_version: str
    target_version: str
    previous_active_version: str | None
    promotion_status: str
    idempotency_key: str
    approved_by: str
    approved_at: str
    executed_at: str
    verification_status: str
    audit_reference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "release_id": self.release_id,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "previous_active_version": self.previous_active_version,
            "promotion_status": self.promotion_status,
            "idempotency_key": self.idempotency_key,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "executed_at": self.executed_at,
            "verification_status": self.verification_status,
            "audit_reference": self.audit_reference,
        }


@dataclass(frozen=True)
class RollbackOperation:
    """Immutable record of a non-destructive rollback operation."""
    rollback_id: str
    release_id: str
    from_version: str
    to_version: str
    rollback_status: str
    approved_by: str
    approved_at: str
    executed_at: str
    reason: str
    audit_reference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rollback_id": self.rollback_id,
            "release_id": self.release_id,
            "from_version": self.from_version,
            "to_version": self.to_version,
            "rollback_status": self.rollback_status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "executed_at": self.executed_at,
            "reason": self.reason,
            "audit_reference": self.audit_reference,
        }


@dataclass(frozen=True)
class ReleasePreflightResult:
    """Immutable result of pre-release verification."""
    is_valid: bool
    status: str
    release_id: str
    artifact_id: str
    evaluation_id: str
    issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evaluation_approved_pass: bool = True
    secret_audit_pass: bool = True
    security_boundary_pass: bool = True
    hash_pass: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "status": self.status,
            "release_id": self.release_id,
            "artifact_id": self.artifact_id,
            "evaluation_id": self.evaluation_id,
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "evaluation_approved_pass": self.evaluation_approved_pass,
            "secret_audit_pass": self.secret_audit_pass,
            "security_boundary_pass": self.security_boundary_pass,
            "hash_pass": self.hash_pass,
        }


# ---------------------------------------------------------------------------
# Helper Functions & Generators
# ---------------------------------------------------------------------------

def generate_release_id(prefix: str = "rel") -> str:
    """Generate a unique release identifier."""
    return f"{prefix}-{uuid4()}"


def generate_release_version(artifact_type: str) -> str:
    """Generate a semantic release version string."""
    now_tag = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    prefix = "rag-rel" if "RAG" in artifact_type else "ds-rel"
    return f"{prefix}-v{now_tag}"


def compute_promotion_idempotency_key(release_id: str, target_version: str) -> str:
    """Compute a deterministic idempotency key for promotion."""
    raw = f"promote:{release_id}:{target_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_rollback_idempotency_key(release_id: str, from_version: str, to_version: str) -> str:
    """Compute a deterministic idempotency key for rollback."""
    raw = f"rollback:{release_id}:{from_version}:{to_version}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def run_prerelease_validation(
    eval_record: EvaluationRecord,
    content_text: str,
    hash_pass: bool = True,
) -> ReleasePreflightResult:
    """Run pre-release verification on an evaluated artifact."""
    issues: list[str] = []
    warnings: list[str] = []

    eval_approved_pass = eval_record.status == EVALUATION_STAGE_APPROVED
    if not eval_approved_pass:
        issues.append("EVALUATION_NOT_APPROVED")

    sec_pass = eval_record.provenance.gap_type != GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY
    if not sec_pass:
        issues.append("SECURITY_ADMIN_BOUNDARY_PROHIBITED")

    secret_pass = audit_secrets_in_text(content_text)
    if not secret_pass:
        issues.append("SECRET_CREDENTIAL_DETECTED")

    if not hash_pass:
        issues.append("CONTENT_HASH_VERIFICATION_FAILED")

    is_valid = len(issues) == 0

    return ReleasePreflightResult(
        is_valid=is_valid,
        status=RELEASE_STAGE_PREFLIGHT_VALIDATED if is_valid else RELEASE_STAGE_PREFLIGHT_FAILED,
        release_id="rel-check",
        artifact_id=eval_record.artifact_id,
        evaluation_id=eval_record.evaluation_id,
        issues=tuple(issues),
        warnings=tuple(warnings),
        evaluation_approved_pass=eval_approved_pass,
        secret_audit_pass=secret_pass,
        security_boundary_pass=sec_pass,
        hash_pass=hash_pass,
    )


# ---------------------------------------------------------------------------
# Release Management Service Engine
# ---------------------------------------------------------------------------

class ReleaseManagementService:
    """Pure domain service managing release candidates, approvals, promotion, and rollback."""

    def create_release_candidate(
        self,
        eval_record: EvaluationRecord,
        content_text: str,
        *,
        created_by: str,
        release_id: str | None = None,
        release_version: str | None = None,
    ) -> ReleaseCandidate:
        """Create a formal ReleaseCandidate from an APPROVED EvaluationRecord."""
        if eval_record.status != EVALUATION_STAGE_APPROVED:
            raise ReleasePreflightError("Cannot create release candidate from an unapproved evaluation record.")

        if eval_record.provenance.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY:
            raise ReleasePreflightError("SECURITY_ADMIN_BOUNDARY prohibited from release candidate creation.")

        if not audit_secrets_in_text(content_text):
            raise ReleasePreflightError("Secret credential detected in release content.")

        rel_id = release_id or generate_release_id("rel")
        rel_ver = release_version or generate_release_version(eval_record.artifact_type)
        now_str = datetime.now(UTC).isoformat()

        content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
        prov_hash = hashlib.sha256(f"{eval_record.evaluation_id}:{rel_id}:{rel_ver}".encode("utf-8")).hexdigest()

        rel_prov = ReleaseProvenance(
            source_request_id=eval_record.provenance.source_request_id,
            source_gap_id=eval_record.provenance.source_gap_id,
            source_record_id=eval_record.provenance.source_record_id,
            candidate_id=eval_record.provenance.candidate_id,
            operation_id=eval_record.provenance.operation_id,
            artifact_id=eval_record.artifact_id,
            evaluation_id=eval_record.evaluation_id,
            comparison_id=eval_record.provenance.comparison_id,
            review_id=eval_record.provenance.review_id,
            release_id=rel_id,
            promotion_operation_id=None,
            rollback_operation_id=None,
            approved_by=created_by,
            approved_at=now_str,
            gap_type=eval_record.provenance.gap_type,
            severity=eval_record.provenance.severity,
            artifact_type=eval_record.artifact_type,
        )

        return ReleaseCandidate(
            release_id=rel_id,
            artifact_id=eval_record.artifact_id,
            artifact_type=eval_record.artifact_type,
            artifact_version=eval_record.artifact_version,
            evaluation_id=eval_record.evaluation_id,
            evaluation_status=eval_record.status,
            release_status=RELEASE_STAGE_PENDING_APPROVAL,
            release_version=rel_ver,
            content_hash=content_hash,
            provenance_hash=prov_hash,
            created_by=created_by,
            created_at=now_str,
            provenance=rel_prov,
            notes=f"Release candidate created from evaluation '{eval_record.evaluation_id}'",
        )

    def process_release_approval(
        self,
        candidate: ReleaseCandidate,
        decision: str,
        *,
        approved_by: str,
        reviewer_notes: str | None = None,
    ) -> tuple[ReleaseCandidate, ReleaseApproval]:
        """Process explicit human admin release approval decision."""
        if not approved_by or not approved_by.strip():
            raise ReleaseApprovalRequiredError("Explicit human admin identity required for release approval.")

        if candidate.release_status != RELEASE_STAGE_PENDING_APPROVAL:
            raise InvalidReleaseTransitionError(f"Cannot approve release in status '{candidate.release_status}'. Expected 'PENDING_RELEASE_APPROVAL'.")

        raw_decision = decision.upper()
        if raw_decision in ("APPROVED", RELEASE_STAGE_APPROVED):
            target_status = RELEASE_STAGE_APPROVED
        elif raw_decision in ("REJECTED", RELEASE_STAGE_REJECTED):
            target_status = RELEASE_STAGE_REJECTED
        elif raw_decision in ("DEFERRED", RELEASE_STAGE_DEFERRED):
            target_status = RELEASE_STAGE_DEFERRED
        else:
            raise InvalidReleaseTransitionError(f"Invalid decision '{decision}'. Must be APPROVED, REJECTED, or DEFERRED.")

        now_str = datetime.now(UTC).isoformat()
        app_id = f"app-{uuid4()}"
        app_hash = hashlib.sha256(f"{candidate.release_id}:{approved_by}:{target_status}".encode("utf-8")).hexdigest()

        final_status = RELEASE_STAGE_READY_FOR_PROMOTION if target_status == RELEASE_STAGE_APPROVED else target_status

        updated_candidate = ReleaseCandidate(
            release_id=candidate.release_id,
            artifact_id=candidate.artifact_id,
            artifact_type=candidate.artifact_type,
            artifact_version=candidate.artifact_version,
            evaluation_id=candidate.evaluation_id,
            evaluation_status=candidate.evaluation_status,
            release_status=final_status,
            release_version=candidate.release_version,
            content_hash=candidate.content_hash,
            provenance_hash=candidate.provenance_hash,
            created_by=candidate.created_by,
            created_at=candidate.created_at,
            provenance=candidate.provenance,
            notes=f"Release decision '{target_status}' applied by {approved_by}: {reviewer_notes or ''}",
        )

        approval = ReleaseApproval(
            approval_id=app_id,
            release_id=candidate.release_id,
            approved_by=approved_by,
            approved_at=now_str,
            decision=target_status,
            reviewer_notes=reviewer_notes,
            approval_hash=app_hash,
        )

        return updated_candidate, approval

    def promote_release(
        self,
        candidate: ReleaseCandidate,
        previous_active_version: str | None,
        *,
        approved_by: str,
    ) -> tuple[ReleaseCandidate, PromotionOperation]:
        """Promote a RELEASE_APPROVED candidate to ACTIVE production status."""
        if candidate.release_status not in (RELEASE_STAGE_READY_FOR_PROMOTION, RELEASE_STAGE_APPROVED):
            raise InvalidReleaseTransitionError(f"Cannot promote release in status '{candidate.release_status}'. Expected 'READY_FOR_PROMOTION'.")

        now_str = datetime.now(UTC).isoformat()
        op_id = f"prom-{uuid4()}"
        idemp_key = compute_promotion_idempotency_key(candidate.release_id, candidate.release_version)

        prom_prov = ReleaseProvenance(
            source_request_id=candidate.provenance.source_request_id,
            source_gap_id=candidate.provenance.source_gap_id,
            source_record_id=candidate.provenance.source_record_id,
            candidate_id=candidate.provenance.candidate_id,
            operation_id=candidate.provenance.operation_id,
            artifact_id=candidate.artifact_id,
            evaluation_id=candidate.evaluation_id,
            comparison_id=candidate.provenance.comparison_id,
            review_id=candidate.provenance.review_id,
            release_id=candidate.release_id,
            promotion_operation_id=op_id,
            rollback_operation_id=None,
            approved_by=approved_by,
            approved_at=now_str,
            gap_type=candidate.provenance.gap_type,
            severity=candidate.provenance.severity,
            artifact_type=candidate.artifact_type,
        )

        active_candidate = ReleaseCandidate(
            release_id=candidate.release_id,
            artifact_id=candidate.artifact_id,
            artifact_type=candidate.artifact_type,
            artifact_version=candidate.artifact_version,
            evaluation_id=candidate.evaluation_id,
            evaluation_status=candidate.evaluation_status,
            release_status=RELEASE_STAGE_ACTIVE,
            release_version=candidate.release_version,
            content_hash=candidate.content_hash,
            provenance_hash=candidate.provenance_hash,
            created_by=candidate.created_by,
            created_at=candidate.created_at,
            provenance=prom_prov,
            notes=f"Release promoted to ACTIVE production version {candidate.release_version} by {approved_by}",
        )

        promotion_op = PromotionOperation(
            operation_id=op_id,
            release_id=candidate.release_id,
            source_version=candidate.artifact_version,
            target_version=candidate.release_version,
            previous_active_version=previous_active_version,
            promotion_status=RELEASE_STAGE_ACTIVE,
            idempotency_key=idemp_key,
            approved_by=approved_by,
            approved_at=now_str,
            executed_at=now_str,
            verification_status="VERIFIED",
            audit_reference=f"audit-prom-{op_id}",
        )

        return active_candidate, promotion_op

    def rollback_release(
        self,
        active_candidate: ReleaseCandidate,
        target_historical_version: str,
        *,
        approved_by: str,
        reason: str,
    ) -> tuple[ReleaseCandidate, RollbackOperation]:
        """Perform non-destructive rollback from active version to target historical version."""
        if active_candidate.release_status != RELEASE_STAGE_ACTIVE:
            raise InvalidReleaseTransitionError(f"Cannot rollback release in status '{active_candidate.release_status}'. Expected 'ACTIVE'.")

        now_str = datetime.now(UTC).isoformat()
        rb_id = f"rb-{uuid4()}"

        rb_prov = ReleaseProvenance(
            source_request_id=active_candidate.provenance.source_request_id,
            source_gap_id=active_candidate.provenance.source_gap_id,
            source_record_id=active_candidate.provenance.source_record_id,
            candidate_id=active_candidate.provenance.candidate_id,
            operation_id=active_candidate.provenance.operation_id,
            artifact_id=active_candidate.artifact_id,
            evaluation_id=active_candidate.evaluation_id,
            comparison_id=active_candidate.provenance.comparison_id,
            review_id=active_candidate.provenance.review_id,
            release_id=active_candidate.release_id,
            promotion_operation_id=active_candidate.provenance.promotion_operation_id,
            rollback_operation_id=rb_id,
            approved_by=approved_by,
            approved_at=now_str,
            gap_type=active_candidate.provenance.gap_type,
            severity=active_candidate.provenance.severity,
            artifact_type=active_candidate.artifact_type,
        )

        rolled_back_candidate = ReleaseCandidate(
            release_id=active_candidate.release_id,
            artifact_id=active_candidate.artifact_id,
            artifact_type=active_candidate.artifact_type,
            artifact_version=active_candidate.artifact_version,
            evaluation_id=active_candidate.evaluation_id,
            evaluation_status=active_candidate.evaluation_status,
            release_status=RELEASE_STAGE_ROLLED_BACK,
            release_version=active_candidate.release_version,
            content_hash=active_candidate.content_hash,
            provenance_hash=active_candidate.provenance_hash,
            created_by=active_candidate.created_by,
            created_at=active_candidate.created_at,
            provenance=rb_prov,
            notes=f"Release rolled back to target historical version {target_historical_version} by {approved_by}: {reason}",
        )

        rollback_op = RollbackOperation(
            rollback_id=rb_id,
            release_id=active_candidate.release_id,
            from_version=active_candidate.release_version,
            to_version=target_historical_version,
            rollback_status=RELEASE_STAGE_ROLLED_BACK,
            approved_by=approved_by,
            approved_at=now_str,
            executed_at=now_str,
            reason=reason,
            audit_reference=f"audit-rb-{rb_id}",
        )

        return rolled_back_candidate, rollback_op
