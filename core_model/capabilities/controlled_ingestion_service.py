"""Phase 22 — Controlled RAG Ingestion & Dataset Export / Training Preparation Domain Service.

Provides pure domain logic, state machines, pre-flight validation, dry-run plan generation,
secret re-validation, canonical hashing, provenance chain tracking, idempotency checking,
and rollback management for controlled RAG ingestion and dataset export operations.

CRITICAL INVARIANTS:
- Pure domain logic — NO database writes, NO network calls, NO subprocesses.
- NO autonomous learning, NO automatic training, NO automatic vector index insertion.
- Candidate readiness (READY_FOR_INGESTION / READY_FOR_EXPORT) alone NEVER triggers production mutation.
- Explicit authorized human admin approval is mandatory before execution.
- Hard block on SECURITY_ADMIN_BOUNDARY and secret/PII-bearing content.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Sequence
from uuid import uuid4

from core_model.capabilities.candidate_curation_service import (
    DATASET_STATUS_READY_FOR_EXPORT,
    DUPLICATE_EXACT,
    DUPLICATE_PROBABLE,
    CONFLICT_CONFLICTING,
    RAG_STATUS_READY_FOR_INGESTION,
    CandidateProvenance,
    DatasetCandidateStagingRecord,
    RAGCandidateStagingRecord,
)
from core_model.capabilities.knowledge_gap import (
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
    SEVERITY_CRITICAL,
)
from core_model.capabilities.knowledge_gap_governance_service import (
    APPROVAL_APPROVED,
    STATUS_APPROVED,
    GovernanceSecurityError,
)

# ---------------------------------------------------------------------------
# Phase 22 State Constants
# ---------------------------------------------------------------------------

# RAG Ingestion States
RAG_STAGE_PREFLIGHT_VALIDATED = "PREFLIGHT_VALIDATED"
RAG_STAGE_PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
RAG_STAGE_DRY_RUN_READY = "DRY_RUN_READY"
RAG_STAGE_PENDING_APPROVAL = "PENDING_APPROVAL"
RAG_STAGE_APPROVED_FOR_INGESTION = "APPROVED_FOR_INGESTION"
RAG_STAGE_INGESTING = "INGESTING"
RAG_STAGE_INGESTED = "INGESTED"
RAG_STAGE_INGESTION_FAILED = "INGESTION_FAILED"
RAG_STAGE_VERIFIED = "VERIFIED"
RAG_STAGE_VERIFICATION_FAILED = "VERIFICATION_FAILED"
RAG_STAGE_ROLLED_BACK = "ROLLED_BACK"

# Dataset Export States
DATASET_STAGE_PREFLIGHT_VALIDATED = "PREFLIGHT_VALIDATED"
DATASET_STAGE_PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
DATASET_STAGE_EXPORT_DRY_RUN_READY = "EXPORT_DRY_RUN_READY"
DATASET_STAGE_PENDING_APPROVAL = "PENDING_APPROVAL"
DATASET_STAGE_APPROVED_FOR_EXPORT = "APPROVED_FOR_EXPORT"
DATASET_STAGE_EXPORTING = "EXPORTING"
DATASET_STAGE_EXPORTED = "EXPORTED"
DATASET_STAGE_EXPORT_FAILED = "EXPORT_FAILED"
DATASET_STAGE_VERIFIED = "VERIFIED"
DATASET_STAGE_VERIFICATION_FAILED = "VERIFICATION_FAILED"
DATASET_STAGE_ROLLED_BACK = "ROLLED_BACK"

# Allowed State Transitions Maps
RAG_INGESTION_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    RAG_STATUS_READY_FOR_INGESTION: (RAG_STAGE_PREFLIGHT_VALIDATED, RAG_STAGE_PREFLIGHT_FAILED),
    RAG_STAGE_PREFLIGHT_VALIDATED: (RAG_STAGE_DRY_RUN_READY,),
    RAG_STAGE_DRY_RUN_READY: (RAG_STAGE_PENDING_APPROVAL,),
    RAG_STAGE_PENDING_APPROVAL: (RAG_STAGE_APPROVED_FOR_INGESTION, RAG_STAGE_PREFLIGHT_FAILED),
    RAG_STAGE_APPROVED_FOR_INGESTION: (RAG_STAGE_INGESTING, RAG_STAGE_INGESTION_FAILED),
    RAG_STAGE_INGESTING: (RAG_STAGE_INGESTED, RAG_STAGE_INGESTION_FAILED),
    RAG_STAGE_INGESTED: (RAG_STAGE_VERIFIED, RAG_STAGE_VERIFICATION_FAILED, RAG_STAGE_ROLLED_BACK),
    RAG_STAGE_VERIFIED: (RAG_STAGE_ROLLED_BACK,),
    RAG_STAGE_INGESTION_FAILED: (RAG_STAGE_ROLLED_BACK,),
    RAG_STAGE_VERIFICATION_FAILED: (RAG_STAGE_ROLLED_BACK,),
    RAG_STAGE_ROLLED_BACK: (),
    RAG_STAGE_PREFLIGHT_FAILED: (),
}

DATASET_EXPORT_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    DATASET_STATUS_READY_FOR_EXPORT: (DATASET_STAGE_PREFLIGHT_VALIDATED, DATASET_STAGE_PREFLIGHT_FAILED),
    DATASET_STAGE_PREFLIGHT_VALIDATED: (DATASET_STAGE_EXPORT_DRY_RUN_READY,),
    DATASET_STAGE_EXPORT_DRY_RUN_READY: (DATASET_STAGE_PENDING_APPROVAL,),
    DATASET_STAGE_PENDING_APPROVAL: (DATASET_STAGE_APPROVED_FOR_EXPORT, DATASET_STAGE_PREFLIGHT_FAILED),
    DATASET_STAGE_APPROVED_FOR_EXPORT: (DATASET_STAGE_EXPORTING, DATASET_STAGE_EXPORT_FAILED),
    DATASET_STAGE_EXPORTING: (DATASET_STAGE_EXPORTED, DATASET_STAGE_EXPORT_FAILED),
    DATASET_STAGE_EXPORTED: (DATASET_STAGE_VERIFIED, DATASET_STAGE_VERIFICATION_FAILED, DATASET_STAGE_ROLLED_BACK),
    DATASET_STAGE_VERIFIED: (DATASET_STAGE_ROLLED_BACK,),
    DATASET_STAGE_EXPORT_FAILED: (DATASET_STAGE_ROLLED_BACK,),
    DATASET_STAGE_VERIFICATION_FAILED: (DATASET_STAGE_ROLLED_BACK,),
    DATASET_STAGE_ROLLED_BACK: (),
    DATASET_STAGE_PREFLIGHT_FAILED: (),
}

# Secret/Credential Regex Patterns for Phase 22 Secondary Audit Gate
_SECRET_RE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(api[_-]?key|secret|bearer|password|token|auth)\s*[:=]\s*\S+"),
    re.compile(r"bearer\s+[a-zA-Z0-9._\~+/-]+=*", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
)


class ControlledIngestionError(Exception):
    """Base exception for Phase 22 controlled ingestion errors."""


class PreflightValidationError(ControlledIngestionError):
    """Raised when pre-flight validation checks fail."""


class InvalidOperationTransitionError(ControlledIngestionError):
    """Raised on invalid state machine transitions."""


class IngestionApprovalRequiredError(ControlledIngestionError):
    """Raised when attempting production mutation without explicit human admin approval."""


# ---------------------------------------------------------------------------
# Data Models & Immutable Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProvenanceChain:
    """Immutable full provenance chain tracking from request to production artifact.
    
    request_id → gap_id → record_id → candidate_id → operation_id → artifact_id
    """
    source_request_id: str
    source_gap_id: str
    source_record_id: str
    candidate_id: str
    operation_id: str
    artifact_id: str | None
    approved_by: str
    approved_at: str
    gap_type: str
    severity: str
    candidate_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_request_id": self.source_request_id,
            "source_gap_id": self.source_gap_id,
            "source_record_id": self.source_record_id,
            "candidate_id": self.candidate_id,
            "operation_id": self.operation_id,
            "artifact_id": self.artifact_id,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "gap_type": self.gap_type,
            "severity": self.severity,
            "candidate_type": self.candidate_type,
        }


@dataclass(frozen=True)
class PreflightResult:
    """Immutable report generated by Phase 22 pre-flight verification."""
    is_valid: bool
    status: str
    candidate_id: str
    candidate_type: str
    source_gap_id: str
    source_record_id: str
    issues: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    secret_audit_pass: bool = True
    security_boundary_pass: bool = True
    phase20_approval_pass: bool = True
    phase21_readiness_pass: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "status": self.status,
            "candidate_id": self.candidate_id,
            "candidate_type": self.candidate_type,
            "source_gap_id": self.source_gap_id,
            "source_record_id": self.source_record_id,
            "issues": list(self.issues),
            "warnings": list(self.warnings),
            "secret_audit_pass": self.secret_audit_pass,
            "security_boundary_pass": self.security_boundary_pass,
            "phase20_approval_pass": self.phase20_approval_pass,
            "phase21_readiness_pass": self.phase21_readiness_pass,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class IngestionPlan:
    """Immutable dry-run ingestion plan describing expected target modifications."""
    operation_id: str
    candidate_id: str
    target_space_id: str
    target_source_title: str
    content_hash: str
    provenance_hash: str
    expected_chunk_count: int
    expected_character_count: int
    duplicate_status: str
    conflict_status: str
    is_executable: bool
    created_at: str
    provenance: ProvenanceChain
    plan_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "candidate_id": self.candidate_id,
            "target_space_id": self.target_space_id,
            "target_source_title": self.target_source_title,
            "content_hash": self.content_hash,
            "provenance_hash": self.provenance_hash,
            "expected_chunk_count": self.expected_chunk_count,
            "expected_character_count": self.expected_character_count,
            "duplicate_status": self.duplicate_status,
            "conflict_status": self.conflict_status,
            "is_executable": self.is_executable,
            "created_at": self.created_at,
            "provenance": self.provenance.to_dict(),
            "plan_notes": self.plan_notes,
        }


@dataclass(frozen=True)
class ExportPlan:
    """Immutable dry-run export plan describing expected dataset artifact outputs."""
    operation_id: str
    candidate_id: str
    target_dataset_dir: str
    artifact_version: str
    content_hash: str
    provenance_hash: str
    record_count: int
    manifest_preview: dict[str, Any]
    is_executable: bool
    created_at: str
    provenance: ProvenanceChain
    plan_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "candidate_id": self.candidate_id,
            "target_dataset_dir": self.target_dataset_dir,
            "artifact_version": self.artifact_version,
            "content_hash": self.content_hash,
            "provenance_hash": self.provenance_hash,
            "record_count": self.record_count,
            "manifest_preview": self.manifest_preview,
            "is_executable": self.is_executable,
            "created_at": self.created_at,
            "provenance": self.provenance.to_dict(),
            "plan_notes": self.plan_notes,
        }


@dataclass(frozen=True)
class ControlledOperationRecord:
    """Immutable record of a Phase 22 controlled production operation."""
    operation_id: str
    candidate_id: str
    candidate_type: str
    status: str
    dry_run_executed: bool
    approved_by: str | None
    approved_at: str | None
    approval_notes: str | None
    executed_by: str | None
    executed_at: str | None
    artifact_id: str | None
    artifact_version: str | None
    content_hash: str
    provenance_hash: str
    idempotency_key: str
    rollback_reference_id: str | None
    provenance: ProvenanceChain
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "candidate_id": self.candidate_id,
            "candidate_type": self.candidate_type,
            "status": self.status,
            "dry_run_executed": self.dry_run_executed,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "approval_notes": self.approval_notes,
            "executed_by": self.executed_by,
            "executed_at": self.executed_at,
            "artifact_id": self.artifact_id,
            "artifact_version": self.artifact_version,
            "content_hash": self.content_hash,
            "provenance_hash": self.provenance_hash,
            "idempotency_key": self.idempotency_key,
            "rollback_reference_id": self.rollback_reference_id,
            "provenance": self.provenance.to_dict(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# Pre-Flight Validation Engine & Helper Functions
# ---------------------------------------------------------------------------

def generate_operation_id(prefix: str = "op") -> str:
    """Generate a unique operation identifier."""
    return f"{prefix}-{uuid4()}"


def generate_artifact_version(base_version: str = "1.0.0") -> str:
    """Generate a versioned artifact tag."""
    now_tag = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"v{base_version}-{now_tag}"


def compute_idempotency_key(candidate_id: str, operation_type: str, content_hash: str) -> str:
    """Compute a deterministic idempotency key for an operation."""
    raw = f"{candidate_id}:{operation_type}:{content_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def audit_secrets_in_text(text: str) -> bool:
    """Return True if text is secret-free; False if any credential pattern matches."""
    if not text:
        return True
    for pattern in _SECRET_RE_PATTERNS:
        if pattern.search(text):
            return False
    return True


def run_preflight_validation_rag(
    record: RAGCandidateStagingRecord,
) -> PreflightResult:
    """Run pre-flight verification on a RAG candidate staging record."""
    issues: list[str] = []
    warnings: list[str] = []

    sec_pass = record.provenance.source_gap_type != GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY
    if not sec_pass:
        issues.append("SECURITY_ADMIN_BOUNDARY_PROHIBITED")

    p20_pass = record.provenance.source_stage is not None and len(record.provenance.approved_by) > 0
    if not p20_pass:
        issues.append("MISSING_PHASE20_PROVENANCE_APPROVAL")

    p21_pass = record.status == RAG_STATUS_READY_FOR_INGESTION
    if not p21_pass:
        issues.append(f"CANDIDATE_NOT_READY_FOR_INGESTION: current status={record.status}")

    secret_pass = audit_secrets_in_text(record.title) and audit_secrets_in_text(record.content)
    if not secret_pass:
        issues.append("SECRET_CREDENTIAL_DETECTED_IN_CONTENT")

    if record.duplicate_status == DUPLICATE_EXACT:
        warnings.append("EXACT_DUPLICATE_CANDIDATE")
    if record.conflict_status == CONFLICT_CONFLICTING:
        issues.append("CONFLICTING_CANDIDATE_REQUIRES_RESOLUTION")

    is_valid = len(issues) == 0

    return PreflightResult(
        is_valid=is_valid,
        status=RAG_STAGE_PREFLIGHT_VALIDATED if is_valid else RAG_STAGE_PREFLIGHT_FAILED,
        candidate_id=record.candidate_id,
        candidate_type="RAG_CANDIDATE",
        source_gap_id=record.provenance.source_gap_id,
        source_record_id=record.provenance.source_record_id,
        issues=tuple(issues),
        warnings=tuple(warnings),
        secret_audit_pass=secret_pass,
        security_boundary_pass=sec_pass,
        phase20_approval_pass=p20_pass,
        phase21_readiness_pass=p21_pass,
        metadata={"title": record.title, "content_hash": record.content_hash},
    )


def run_preflight_validation_dataset(
    record: DatasetCandidateStagingRecord,
) -> PreflightResult:
    """Run pre-flight verification on a Dataset candidate staging record."""
    issues: list[str] = []
    warnings: list[str] = []

    sec_pass = record.provenance.source_gap_type != GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY
    if not sec_pass:
        issues.append("SECURITY_ADMIN_BOUNDARY_PROHIBITED")

    p20_pass = record.provenance.source_stage is not None and len(record.provenance.approved_by) > 0
    if not p20_pass:
        issues.append("MISSING_PHASE20_PROVENANCE_APPROVAL")

    p21_pass = record.status == DATASET_STATUS_READY_FOR_EXPORT
    if not p21_pass:
        issues.append(f"CANDIDATE_NOT_READY_FOR_EXPORT: current status={record.status}")

    secret_pass = audit_secrets_in_text(record.input_context) and audit_secrets_in_text(record.proposed_output)
    if not secret_pass:
        issues.append("SECRET_CREDENTIAL_DETECTED_IN_CONTENT")

    if record.duplicate_status == DUPLICATE_EXACT:
        warnings.append("EXACT_DUPLICATE_CANDIDATE")
    if record.conflict_status == CONFLICT_CONFLICTING:
        issues.append("CONFLICTING_CANDIDATE_REQUIRES_RESOLUTION")

    is_valid = len(issues) == 0

    return PreflightResult(
        is_valid=is_valid,
        status=DATASET_STAGE_PREFLIGHT_VALIDATED if is_valid else DATASET_STAGE_PREFLIGHT_FAILED,
        candidate_id=record.candidate_id,
        candidate_type="DATASET_CANDIDATE",
        source_gap_id=record.provenance.source_gap_id,
        source_record_id=record.provenance.source_record_id,
        issues=tuple(issues),
        warnings=tuple(warnings),
        secret_audit_pass=secret_pass,
        security_boundary_pass=sec_pass,
        phase20_approval_pass=p20_pass,
        phase21_readiness_pass=p21_pass,
        metadata={"domain_topic": record.domain_topic, "language": record.language},
    )


# ---------------------------------------------------------------------------
# Domain State Machine Class
# ---------------------------------------------------------------------------

class ControlledIngestionService:
    """Pure domain service for Phase 22 controlled ingestion and export operations."""

    def create_rag_dry_run_plan(
        self,
        record: RAGCandidateStagingRecord,
        *,
        target_space_id: str = "space-default",
        operation_id: str | None = None,
    ) -> tuple[PreflightResult, IngestionPlan]:
        """Generate a dry-run ingestion plan without mutating any state."""
        preflight = run_preflight_validation_rag(record)
        if not preflight.is_valid:
            raise PreflightValidationError(f"Preflight validation failed: {preflight.issues}")

        op_id = operation_id or generate_operation_id("op-rag")

        prov = ProvenanceChain(
            source_request_id=record.provenance.source_request_id,
            source_gap_id=record.provenance.source_gap_id,
            source_record_id=record.provenance.source_record_id,
            candidate_id=record.candidate_id,
            operation_id=op_id,
            artifact_id=None,
            approved_by=record.provenance.approved_by,
            approved_at=record.provenance.approved_at,
            gap_type=record.provenance.source_gap_type,
            severity=record.provenance.source_severity,
            candidate_type="RAG_CANDIDATE",
        )

        plan = IngestionPlan(
            operation_id=op_id,
            candidate_id=record.candidate_id,
            target_space_id=target_space_id,
            target_source_title=record.title,
            content_hash=record.content_hash,
            provenance_hash=record.provenance_hash,
            expected_chunk_count=max(1, len(record.content) // 500),
            expected_character_count=len(record.content),
            duplicate_status=record.duplicate_status,
            conflict_status=record.conflict_status,
            is_executable=True,
            created_at=datetime.now(UTC).isoformat(),
            provenance=prov,
            plan_notes="Dry-run ingestion plan ready for human admin review",
        )

        return preflight, plan

    def create_dataset_dry_run_plan(
        self,
        record: DatasetCandidateStagingRecord,
        *,
        target_dataset_dir: str = "data/dataset_exports",
        operation_id: str | None = None,
    ) -> tuple[PreflightResult, ExportPlan]:
        """Generate a dry-run export plan without mutating any state."""
        preflight = run_preflight_validation_dataset(record)
        if not preflight.is_valid:
            raise PreflightValidationError(f"Preflight validation failed: {preflight.issues}")

        op_id = operation_id or generate_operation_id("op-ds")
        art_ver = generate_artifact_version(record.candidate_version)

        prov = ProvenanceChain(
            source_request_id=record.provenance.source_request_id,
            source_gap_id=record.provenance.source_gap_id,
            source_record_id=record.provenance.source_record_id,
            candidate_id=record.candidate_id,
            operation_id=op_id,
            artifact_id=f"art-{op_id}",
            approved_by=record.provenance.approved_by,
            approved_at=record.provenance.approved_at,
            gap_type=record.provenance.source_gap_type,
            severity=record.provenance.source_severity,
            candidate_type="DATASET_CANDIDATE",
        )

        manifest_preview = {
            "candidate_id": record.candidate_id,
            "domain_topic": record.domain_topic,
            "language": record.language,
            "version": art_ver,
            "files": ["manifest.json", "records.jsonl", "provenance.json", "checksums.json"],
        }

        plan = ExportPlan(
            operation_id=op_id,
            candidate_id=record.candidate_id,
            target_dataset_dir=target_dataset_dir,
            artifact_version=art_ver,
            content_hash=record.content_hash,
            provenance_hash=record.provenance_hash,
            record_count=1,
            manifest_preview=manifest_preview,
            is_executable=True,
            created_at=datetime.now(UTC).isoformat(),
            provenance=prov,
            plan_notes="Dry-run export plan ready for human admin review",
        )

        return preflight, plan

    def approve_operation(
        self,
        op_record: ControlledOperationRecord,
        *,
        approver_id: str,
        approval_notes: str | None = None,
    ) -> ControlledOperationRecord:
        """Approve a dry-run operation plan, advancing state to APPROVED_FOR_*."""
        if not approver_id or not approver_id.strip():
            raise IngestionApprovalRequiredError("Explicit admin identity required for approval.")

        if op_record.candidate_type == "RAG_CANDIDATE":
            allowed = RAG_INGESTION_ALLOWED_TRANSITIONS.get(op_record.status, ())
            target_status = RAG_STAGE_APPROVED_FOR_INGESTION
        else:
            allowed = DATASET_EXPORT_ALLOWED_TRANSITIONS.get(op_record.status, ())
            target_status = DATASET_STAGE_APPROVED_FOR_EXPORT

        if target_status not in allowed:
            raise InvalidOperationTransitionError(
                f"Cannot approve operation {op_record.operation_id} from status '{op_record.status}'. Allowed: {allowed}"
            )

        now_str = datetime.now(UTC).isoformat()
        notes = (op_record.approval_notes or "") + (f"; Approved by {approver_id}: {approval_notes}" if approval_notes else "")

        return ControlledOperationRecord(
            operation_id=op_record.operation_id,
            candidate_id=op_record.candidate_id,
            candidate_type=op_record.candidate_type,
            status=target_status,
            dry_run_executed=op_record.dry_run_executed,
            approved_by=approver_id,
            approved_at=now_str,
            approval_notes=notes,
            executed_by=op_record.executed_by,
            executed_at=op_record.executed_at,
            artifact_id=op_record.artifact_id,
            artifact_version=op_record.artifact_version,
            content_hash=op_record.content_hash,
            provenance_hash=op_record.provenance_hash,
            idempotency_key=op_record.idempotency_key,
            rollback_reference_id=op_record.rollback_reference_id,
            provenance=op_record.provenance,
            created_at=op_record.created_at,
            updated_at=now_str,
        )

    def transition_operation(
        self,
        op_record: ControlledOperationRecord,
        to_status: str,
        *,
        actor_id: str | None = None,
        artifact_id: str | None = None,
        rollback_ref: str | None = None,
    ) -> ControlledOperationRecord:
        """Validate and apply state machine transition for controlled operation."""
        if op_record.candidate_type == "RAG_CANDIDATE":
            allowed = RAG_INGESTION_ALLOWED_TRANSITIONS.get(op_record.status, ())
        else:
            allowed = DATASET_EXPORT_ALLOWED_TRANSITIONS.get(op_record.status, ())

        if to_status not in allowed:
            raise InvalidOperationTransitionError(
                f"Cannot transition operation {op_record.operation_id} from status '{op_record.status}' to '{to_status}'. Allowed: {allowed}"
            )

        now_str = datetime.now(UTC).isoformat()
        exec_by = actor_id or op_record.executed_by
        art_id = artifact_id or op_record.artifact_id
        r_ref = rollback_ref or op_record.rollback_reference_id

        return ControlledOperationRecord(
            operation_id=op_record.operation_id,
            candidate_id=op_record.candidate_id,
            candidate_type=op_record.candidate_type,
            status=to_status,
            dry_run_executed=op_record.dry_run_executed,
            approved_by=op_record.approved_by,
            approved_at=op_record.approved_at,
            approval_notes=op_record.approval_notes,
            executed_by=exec_by,
            executed_at=now_str if to_status in (RAG_STAGE_INGESTED, DATASET_STAGE_EXPORTED, RAG_STAGE_VERIFIED, DATASET_STAGE_VERIFIED) else op_record.executed_at,
            artifact_id=art_id,
            artifact_version=op_record.artifact_version,
            content_hash=op_record.content_hash,
            provenance_hash=op_record.provenance_hash,
            idempotency_key=op_record.idempotency_key,
            rollback_reference_id=r_ref,
            provenance=op_record.provenance,
            created_at=op_record.created_at,
            updated_at=now_str,
        )
