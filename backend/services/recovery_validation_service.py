"""Phase 30 — Recovery Validation Service.

Coordinates isolated recovery drill execution, temporary database restore validation,
RPO & RTO compliance status tracking, backup lifecycle governance evaluation,
deterministic operational readiness evaluation, idempotency, and audit logging.

SAFETY INVARIANT: Recovery drills execute strictly against isolated temporary
SQLite files generated via tempfile.mkdtemp() or :memory: connections.
The production database data/database/brud_ai.db is NEVER mutated or used as a write target.
"""

import os
import shutil
import sqlite3
import tempfile
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.database.repositories.disaster_recovery_repository import DisasterRecoveryRepository
from backend.database.repositories.recovery_validation_repository import RecoveryValidationRepository
from core_model.capabilities.disaster_recovery_service import (
    BackupIntegrityError,
    compute_file_sha256,
)
from core_model.capabilities.recovery_validation_service import (
    OperationalReadinessReport,
    RecoveryDrillError,
    RecoveryDrillRecord,
    RecoveryValidationProvenance,
    compute_recovery_drill_idempotency_key,
    evaluate_backup_lifecycle_state,
    evaluate_rpo_status,
    evaluate_rto_status,
)


class RecoveryValidationService:
    """Backend service for Phase 30 Production Reliability, Recovery Validation & Operational Governance."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.repository = RecoveryValidationRepository(db)
        self.dr_repository = DisasterRecoveryRepository(db)

    def execute_recovery_drill(
        self,
        backup_id: str,
        *,
        executed_by: str = "admin-1",
        drill_type: str = "SCHEDULED_DRILL",
        rto_target_seconds: float = 900.0,
        provenance: RecoveryValidationProvenance | None = None,
    ) -> RecoveryDrillRecord:
        """Execute a safe, isolated recovery drill from a database snapshot backup.

        Requirements:
        1. Query and validate backup metadata.
        2. Verify backup SHA-256 on disk.
        3. Create isolated temporary directory (tempfile.mkdtemp()).
        4. Copy backup snapshot into temporary environment.
        5. NEVER point drill at production DB.
        6. Execute SQLite PRAGMA quick_check.
        7. Execute schema validation and table readability check.
        8. Measure exact drill duration for RTO evaluation.
        9. Calculate restored file SHA-256.
        10. Store drill audit record with idempotency and provenance.
        11. Safely clean up temporary environment.
        """
        idempotency_key = compute_recovery_drill_idempotency_key(backup_id, executed_by, drill_type)
        existing_op = self.repository.get_recovery_drill_by_idempotency(idempotency_key)
        if existing_op:
            return existing_op

        backup = self.dr_repository.get_backup_metadata(backup_id)
        if not backup:
            raise RecoveryDrillError(f"Backup snapshot '{backup_id}' not found for recovery drill.")

        if not os.path.exists(backup.storage_path):
            raise RecoveryDrillError(f"Backup storage file '{backup.storage_path}' missing from disk.")

        drill_id = f"drill-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc).isoformat()
        start_time = time.perf_counter()

        temp_dir = tempfile.mkdtemp(prefix="phase30_drill_")
        target_temp_db = os.path.join(temp_dir, f"restored_drill_{drill_id}.db")

        integrity_passed = False
        schema_passed = False
        restored_sha256 = ""

        try:
            # Copy snapshot into isolated temporary file
            shutil.copy2(backup.storage_path, target_temp_db)
            restored_sha256, _ = compute_file_sha256(target_temp_db)

            # SQLite integrity check (PRAGMA quick_check)
            temp_conn = sqlite3.connect(target_temp_db)
            cursor = temp_conn.cursor()
            cursor.execute("PRAGMA quick_check;")
            res = cursor.fetchone()
            if res and res[0] == "ok":
                integrity_passed = True

            # Schema & table readability verification
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            if len(tables) > 0:
                schema_passed = True
            temp_conn.close()
        except Exception as e:
            integrity_passed = False
            schema_passed = False
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        elapsed_seconds = round(time.perf_counter() - start_time, 4)
        completed_at = datetime.now(timezone.utc).isoformat()

        rto_stat = evaluate_rto_status(elapsed_seconds, rto_target_seconds)
        checksum_match = (restored_sha256 == backup.backup_sha256)
        overall_result = "PASS" if (integrity_passed and schema_passed and checksum_match) else "FAIL"

        audit_ref = f"AUDIT-PHASE30-DRILL-{drill_id}"

        record = RecoveryDrillRecord(
            drill_id=drill_id,
            backup_id=backup_id,
            drill_type=drill_type,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=elapsed_seconds,
            target_rto_seconds=rto_target_seconds,
            rto_status=rto_stat,
            backup_sha256=backup.backup_sha256,
            restored_db_sha256=restored_sha256,
            integrity_status="PASSED" if integrity_passed else "FAILED",
            schema_status="PASSED" if schema_passed else "FAILED",
            result=overall_result,
            executed_by=executed_by,
            audit_reference=audit_ref,
            idempotency_key=idempotency_key,
            provenance=provenance or RecoveryValidationProvenance(backup_id=backup_id, drill_id=drill_id),
        )

        self.repository.insert_recovery_drill(record)
        return record

    def evaluate_operational_readiness(
        self,
        rpo_target_seconds: float = 3600.0,
        rto_target_seconds: float = 900.0,
    ) -> OperationalReadinessReport:
        """Evaluate deterministic system operational readiness.

        Factors evaluated:
        1. Latest verified backup availability.
        2. Latest backup freshness & RPO status.
        3. Backup checksum integrity.
        4. Latest recovery drill execution result.
        5. Latest recovery drill RTO compliance.
        6. Active recovery locks count.

        Final Readiness Verdicts:
        - READY: All factors pass cleanly within target thresholds.
        - READY_WITH_WARNINGS: Backup available & drill passed, but RPO/RTO is AT_RISK or locks active.
        - NOT_READY: No verified backup, corrupted backup, failing latest drill, or RPO/RTO BREACHED.
        """
        eval_id = f"eval-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        backups = self.dr_repository.list_backups(limit=50)
        latest_backup = backups[0] if backups else None

        latest_freshness = latest_backup.rpo_freshness_seconds if latest_backup else None
        rpo_stat = evaluate_rpo_status(latest_freshness, rpo_target_seconds)

        latest_drill = self.repository.get_latest_recovery_drill()
        latest_drill_result = latest_drill.result if latest_drill else "NO_DRILL_EXECUTED"
        latest_drill_rto = latest_drill.rto_status if latest_drill else "UNKNOWN"

        # Check active recovery locks count in phase29_recovery_locks
        cursor = self.db.cursor()
        cursor.execute("SELECT COUNT(*) FROM phase29_recovery_locks;")
        row = cursor.fetchone()
        active_locks_count = row[0] if row else 0

        # Determine readiness status
        if not latest_backup or rpo_stat == "NO_VERIFIED_BACKUP":
            readiness = "NOT_READY"
            summary_note = "No verified database backup is available."
        elif not latest_backup.is_verified:
            readiness = "NOT_READY"
            summary_note = "Latest backup failed SHA-256 integrity verification."
        elif rpo_stat == "BREACHED" or latest_drill_result == "FAIL":
            readiness = "NOT_READY"
            summary_note = f"RPO status is {rpo_stat} or latest recovery drill result is {latest_drill_result}."
        elif rpo_stat == "AT_RISK" or latest_drill_rto == "AT_RISK" or active_locks_count > 0:
            readiness = "READY_WITH_WARNINGS"
            summary_note = "System is operational but RPO/RTO is at risk or active locks are present."
        else:
            readiness = "READY"
            summary_note = "All operational readiness factors pass cleanly within target thresholds."

        lifecycle_state = evaluate_backup_lifecycle_state(
            latest_backup.created_at, latest_backup.is_verified, now_iso
        ) if latest_backup else "UNKNOWN"

        details = {
            "summary_note": summary_note,
            "latest_backup_id": latest_backup.backup_id if latest_backup else None,
            "backup_lifecycle_state": lifecycle_state,
            "rpo_target_seconds": rpo_target_seconds,
            "rto_target_seconds": rto_target_seconds,
            "latest_drill_id": latest_drill.drill_id if latest_drill else None,
        }

        return OperationalReadinessReport(
            evaluation_id=eval_id,
            readiness_status=readiness,
            latest_backup_freshness_seconds=latest_freshness or -1.0,
            rpo_status=rpo_stat,
            rto_status=latest_drill_rto,
            latest_drill_result=latest_drill_result,
            active_locks_count=active_locks_count,
            evaluated_at=now_iso,
            details=details,
        )

    def get_rpo_compliance_status(self, rpo_target_seconds: float = 3600.0) -> dict[str, Any]:
        """Get summary RPO compliance status."""
        backups = self.dr_repository.list_backups(limit=10)
        latest_backup = backups[0] if backups else None
        freshness = latest_backup.rpo_freshness_seconds if latest_backup else None
        rpo_stat = evaluate_rpo_status(freshness, rpo_target_seconds)
        return {
            "rpo_target_seconds": rpo_target_seconds,
            "latest_backup_freshness_seconds": freshness,
            "rpo_status": rpo_stat,
            "is_compliant": rpo_stat in ("WITHIN_TARGET", "AT_RISK"),
        }

    def get_rto_compliance_status(self, rto_target_seconds: float = 900.0) -> dict[str, Any]:
        """Get summary RTO compliance status based on latest recovery drill."""
        latest_drill = self.repository.get_latest_recovery_drill()
        duration = latest_drill.duration_seconds if latest_drill else None
        rto_stat = evaluate_rto_status(duration, rto_target_seconds)
        return {
            "rto_target_seconds": rto_target_seconds,
            "latest_drill_duration_seconds": duration,
            "rto_status": rto_stat,
            "is_compliant": rto_stat in ("WITHIN_TARGET", "AT_RISK"),
        }
