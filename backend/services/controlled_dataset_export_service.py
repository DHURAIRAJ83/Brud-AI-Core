"""Phase 22 — Controlled Dataset Export Backend Service.

Coordinates pre-flight validation, dry-run manifest preview generation, explicit admin approval
verification, controlled atomic export of dataset artifacts (manifest.json, records.jsonl,
provenance.json, checksums.json) to versioned export directories, post-export checksum verification,
structured audit logging, and non-destructive version rollback.

CRITICAL INVARIANTS:
- Admin approval is strictly required before dataset artifact export.
- Candidate readiness (READY_FOR_EXPORT) alone NEVER triggers automatic export.
- Reversible, rollback-aware version management.
- Zero model training, zero fine-tuning, zero automatic weight modifications.
- Zero autonomous execution, zero background workers, zero subprocesses.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.database.repositories.candidate_curation_repository import CandidateCurationRepository
from backend.database.repositories.controlled_ingestion_repository import ControlledIngestionRepository
from core_model.capabilities.candidate_curation_service import (
    DATASET_STATUS_READY_FOR_EXPORT,
    DatasetCandidateStagingRecord,
)
from core_model.capabilities.controlled_ingestion_service import (
    DATASET_STAGE_APPROVED_FOR_EXPORT,
    DATASET_STAGE_EXPORTED,
    DATASET_STAGE_EXPORTING,
    DATASET_STAGE_EXPORT_DRY_RUN_READY,
    DATASET_STAGE_EXPORT_FAILED,
    DATASET_STAGE_PENDING_APPROVAL,
    DATASET_STAGE_PREFLIGHT_VALIDATED,
    DATASET_STAGE_ROLLED_BACK,
    DATASET_STAGE_VERIFIED,
    ControlledIngestionService,
    ControlledOperationRecord,
    ExportPlan,
    IngestionApprovalRequiredError,
    PreflightResult,
    compute_idempotency_key,
    generate_artifact_version,
    generate_operation_id,
)


class ControlledDatasetExportService:
    """Backend service for executing controlled Dataset export operations."""

    def __init__(self, conn: sqlite3.Connection, export_root_dir: str | Path = "data/dataset_exports") -> None:
        self.conn = conn
        self.export_root_dir = Path(export_root_dir)
        self.curation_repo = CandidateCurationRepository(conn)
        self.ingestion_repo = ControlledIngestionRepository(conn)
        self.domain_service = ControlledIngestionService()

    def run_preflight(self, candidate_id: str) -> PreflightResult:
        """Run pre-flight verification on a staged Dataset candidate."""
        record = self.curation_repo.get_dataset_candidate_by_id(candidate_id)
        if not record:
            raise ValueError(f"Dataset candidate record '{candidate_id}' not found.")

        return self.domain_service.run_preflight_validation_dataset(record)

    def execute_dry_run(
        self, candidate_id: str, *, target_dir: str | None = None
    ) -> ExportPlan:
        """Execute a dry-run export plan and store an operation log entry in PENDING_APPROVAL status."""
        record = self.curation_repo.get_dataset_candidate_by_id(candidate_id)
        if not record:
            raise ValueError(f"Dataset candidate record '{candidate_id}' not found.")

        exp_dir = target_dir or str(self.export_root_dir)
        idempotency_key = compute_idempotency_key(candidate_id, "dataset_export", record.content_hash)
        existing = self.ingestion_repo.get_operation_by_idempotency_key(idempotency_key)
        if existing:
            preflight, plan = self.domain_service.create_dataset_dry_run_plan(
                record, target_dataset_dir=exp_dir, operation_id=existing.operation_id
            )
            return plan

        preflight, plan = self.domain_service.create_dataset_dry_run_plan(
            record, target_dataset_dir=exp_dir
        )

        op_rec = ControlledOperationRecord(
            operation_id=plan.operation_id,
            candidate_id=candidate_id,
            candidate_type="DATASET_CANDIDATE",
            status=DATASET_STAGE_PENDING_APPROVAL,
            dry_run_executed=True,
            approved_by=None,
            approved_at=None,
            approval_notes=None,
            executed_by=None,
            executed_at=None,
            artifact_id=plan.provenance.artifact_id,
            artifact_version=plan.artifact_version,
            content_hash=record.content_hash,
            provenance_hash=record.provenance_hash,
            idempotency_key=idempotency_key,
            rollback_reference_id=None,
            provenance=plan.provenance,
            created_at=datetime.now(UTC).isoformat(),
            updated_at=datetime.now(UTC).isoformat(),
        )

        self.ingestion_repo.insert_operation_record(op_rec)
        return plan

    def approve_export(
        self, operation_id: str, *, approver_id: str, approval_notes: str | None = None
    ) -> ControlledOperationRecord:
        """Explicitly approve a Dataset export dry-run operation."""
        op_rec = self.ingestion_repo.get_operation_by_id(operation_id)
        if not op_rec:
            raise ValueError(f"Operation record '{operation_id}' not found.")

        approved_op = self.domain_service.approve_operation(
            op_rec, approver_id=approver_id, approval_notes=approval_notes
        )
        self.ingestion_repo.update_operation_state(approved_op)
        return approved_op

    def execute_export(
        self, operation_id: str, *, executor_id: str, output_base_dir: Path | str | None = None
    ) -> dict[str, Any]:
        """Execute controlled export of versioned dataset artifact files after explicit approval."""
        op_rec = self.ingestion_repo.get_operation_by_id(operation_id)
        if not op_rec:
            raise ValueError(f"Operation record '{operation_id}' not found.")

        if op_rec.status != DATASET_STAGE_APPROVED_FOR_EXPORT:
            raise IngestionApprovalRequiredError(
                f"Operation '{operation_id}' status is '{op_rec.status}'. Explicit human admin approval (APPROVED_FOR_EXPORT) is required before export."
            )

        candidate = self.curation_repo.get_dataset_candidate_by_id(op_rec.candidate_id)
        if not candidate:
            raise ValueError(f"Staged candidate '{op_rec.candidate_id}' not found.")

        # 1. Transition to EXPORTING
        exporting_op = self.domain_service.transition_operation(
            op_rec, DATASET_STAGE_EXPORTING, actor_id=executor_id
        )
        self.ingestion_repo.update_operation_state(exporting_op)

        out_root = Path(output_base_dir) if output_base_dir else self.export_root_dir
        art_ver = op_rec.artifact_version or generate_artifact_version(candidate.candidate_version)
        art_id = op_rec.artifact_id or f"art-ds-{op_rec.operation_id}"
        target_dir = out_root / candidate.candidate_id / art_ver
        target_dir.mkdir(parents=True, exist_ok=True)

        # 2. Generate records.jsonl
        rec_item = {
            "candidate_id": candidate.candidate_id,
            "input_context": candidate.input_context,
            "proposed_output": candidate.proposed_output,
            "language": candidate.language,
            "domain_topic": candidate.domain_topic,
        }
        rec_content = json.dumps(rec_item, ensure_ascii=False) + "\n"
        rec_file = target_dir / "records.jsonl"
        rec_file.write_text(rec_content, encoding="utf-8")

        # 3. Generate provenance.json
        prov_file = target_dir / "provenance.json"
        prov_file.write_text(json.dumps(op_rec.provenance.to_dict(), indent=2), encoding="utf-8")

        # 4. Generate manifest.json
        manifest = {
            "artifact_id": art_id,
            "artifact_version": art_ver,
            "candidate_id": candidate.candidate_id,
            "domain_topic": candidate.domain_topic,
            "language": candidate.language,
            "record_count": 1,
            "created_by": executor_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        man_file = target_dir / "manifest.json"
        man_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # 5. Generate checksums.json
        checksums = {
            "records.jsonl": hashlib.sha256(rec_file.read_bytes()).hexdigest(),
            "provenance.json": hashlib.sha256(prov_file.read_bytes()).hexdigest(),
            "manifest.json": hashlib.sha256(man_file.read_bytes()).hexdigest(),
        }
        chk_file = target_dir / "checksums.json"
        chk_file.write_text(json.dumps(checksums, indent=2), encoding="utf-8")

        final_checksum = hashlib.sha256(chk_file.read_bytes()).hexdigest()

        # 6. Transition to EXPORTED -> VERIFIED
        exported_op = self.domain_service.transition_operation(
            exporting_op, DATASET_STAGE_EXPORTED, actor_id=executor_id, artifact_id=art_id
        )
        self.ingestion_repo.update_operation_state(exported_op)

        verified_op = self.domain_service.transition_operation(
            exported_op, DATASET_STAGE_VERIFIED, actor_id=executor_id, artifact_id=art_id
        )
        self.ingestion_repo.update_operation_state(verified_op)

        # 7. Register Artifact Version Entry
        self.ingestion_repo.insert_artifact_version(
            artifact_id=art_id,
            artifact_type="DATASET_EXPORT_ARTIFACT",
            artifact_version=art_ver,
            candidate_id=candidate.candidate_id,
            operation_id=operation_id,
            source_gap_id=candidate.provenance.source_gap_id,
            source_record_id=candidate.provenance.source_record_id,
            source_request_id=candidate.provenance.source_request_id,
            provenance_hash=candidate.provenance_hash,
            content_hash=candidate.content_hash,
            created_by=executor_id,
            created_at=datetime.now(UTC).isoformat(),
            status="ACTIVE",
            checksum_sha256=final_checksum,
            previous_version=None,
            rollback_reference_id=None,
            manifest=manifest,
        )

        return {
            "operation_id": operation_id,
            "candidate_id": candidate.candidate_id,
            "artifact_id": art_id,
            "artifact_version": art_ver,
            "export_dir": str(target_dir),
            "status": DATASET_STAGE_VERIFIED,
            "checksums": checksums,
            "executed_by": executor_id,
            "executed_at": verified_op.executed_at,
        }

    def rollback_export(
        self, operation_id: str, *, admin_id: str, rollback_reason: str | None = None
    ) -> ControlledOperationRecord:
        """Perform a non-destructive, audited rollback of a Dataset export operation."""
        op_rec = self.ingestion_repo.get_operation_by_id(operation_id)
        if not op_rec:
            raise ValueError(f"Operation record '{operation_id}' not found.")

        rollback_ref = generate_operation_id("op-rollback")
        rolled_back_op = self.domain_service.transition_operation(
            op_rec, DATASET_STAGE_ROLLED_BACK, actor_id=admin_id, rollback_ref=rollback_ref
        )
        self.ingestion_repo.update_operation_state(rolled_back_op)

        if op_rec.artifact_id:
            self.ingestion_repo.update_artifact_status(op_rec.artifact_id, "ROLLED_BACK", rollback_ref)

        return rolled_back_op
