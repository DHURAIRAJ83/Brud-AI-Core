"""Phase 29 — Disaster Recovery Service.

Coordinates database snapshot backup creation, SHA-256 integrity verification,
preflight restore checks, human-authorized restore execution, idempotency, and audit logging.
"""

import os
import shutil
import sqlite3
import uuid
from datetime import datetime, timezone

from backend.database.repositories.disaster_recovery_repository import DisasterRecoveryRepository
from core_model.capabilities.disaster_recovery_service import (
    BackupIntegrityError,
    BackupMetadataRecord,
    DisasterRecoveryProvenance,
    RestoreError,
    RestoreOperationRecord,
    RestorePreflightReport,
    calculate_rpo_freshness,
    compute_disaster_recovery_idempotency_key,
    compute_file_sha256,
)


class DisasterRecoveryService:
    """Backend service for Phase 29 Disaster Recovery & Business Continuity."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.repository = DisasterRecoveryRepository(db)

    def create_database_snapshot(
        self,
        source_db_path: str,
        backup_dir: str,
        *,
        created_by: str = "admin-1",
        backup_type: str = "FULL_SNAPSHOT",
        provenance: DisasterRecoveryProvenance | None = None,
    ) -> BackupMetadataRecord:
        """Create a full snapshot backup of a target database and record SHA-256 metadata."""
        if not os.path.exists(source_db_path):
            raise BackupIntegrityError(f"Source database file '{source_db_path}' does not exist.")

        os.makedirs(backup_dir, exist_ok=True)
        backup_id = f"bak-{uuid.uuid4().hex[:8]}"
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dest_filename = f"brud_ai_backup_{timestamp_str}_{backup_id}.db"
        dest_path = os.path.join(backup_dir, dest_filename)

        # Compute source DB SHA-256
        source_sha256, _ = compute_file_sha256(source_db_path)

        # Safely copy database file
        shutil.copy2(source_db_path, dest_path)

        # Compute backup DB SHA-256 and size
        backup_sha256, backup_size = compute_file_sha256(dest_path)

        if source_sha256 != backup_sha256:
            raise BackupIntegrityError("Backup snapshot creation failed: SHA-256 checksum mismatch.")

        now_iso = datetime.now(timezone.utc).isoformat()
        freshness_sec, _ = calculate_rpo_freshness(now_iso, now_iso)

        record = BackupMetadataRecord(
            backup_id=backup_id,
            backup_type=backup_type,
            source_db_sha256=source_sha256,
            backup_sha256=backup_sha256,
            backup_size_bytes=backup_size,
            created_at=now_iso,
            storage_path=dest_path,
            rpo_freshness_seconds=freshness_sec,
            is_verified=True,
            created_by=created_by,
            provenance=provenance or DisasterRecoveryProvenance(backup_id=backup_id),
        )

        self.repository.insert_backup_metadata(record)
        return record

    def verify_backup_integrity(self, backup_id: str) -> bool:
        """Verify that a stored backup file exists and matches its recorded SHA-256 checksum."""
        backup = self.repository.get_backup_metadata(backup_id)
        if not backup:
            raise BackupIntegrityError(f"Backup record '{backup_id}' not found.")

        if not os.path.exists(backup.storage_path):
            self.repository.update_backup_verification_status(backup_id, False)
            return False

        computed_sha256, computed_size = compute_file_sha256(backup.storage_path)
        is_valid = (computed_sha256 == backup.backup_sha256) and (computed_size == backup.backup_size_bytes)

        self.repository.update_backup_verification_status(backup_id, is_valid)
        return is_valid

    def preflight_restore_check(
        self,
        backup_id: str,
        provenance: DisasterRecoveryProvenance | None = None,
    ) -> RestorePreflightReport:
        """Perform dry-run preflight inspection prior to restore execution.

        Inspection ONLY observes and reports. Zero filesystem or database mutation.
        """
        backup = self.repository.get_backup_metadata(backup_id)
        if not backup:
            return RestorePreflightReport(
                preflight_id=f"pref-{uuid.uuid4().hex[:8]}",
                backup_id=backup_id,
                checksum_match=False,
                integrity_check_passed=False,
                can_restore=False,
                checked_at=datetime.now(timezone.utc).isoformat(),
                notes=f"Backup record '{backup_id}' not found.",
                provenance=provenance or DisasterRecoveryProvenance(backup_id=backup_id),
            )

        if not os.path.exists(backup.storage_path):
            return RestorePreflightReport(
                preflight_id=f"pref-{uuid.uuid4().hex[:8]}",
                backup_id=backup_id,
                checksum_match=False,
                integrity_check_passed=False,
                can_restore=False,
                checked_at=datetime.now(timezone.utc).isoformat(),
                notes=f"Backup storage file '{backup.storage_path}' does not exist on disk.",
                provenance=provenance or DisasterRecoveryProvenance(backup_id=backup_id),
            )

        computed_sha256, computed_size = compute_file_sha256(backup.storage_path)
        checksum_match = (computed_sha256 == backup.backup_sha256) and (computed_size == backup.backup_size_bytes)

        # Deep SQLite integrity check (PRAGMA quick_check)
        integrity_passed = False
        try:
            temp_conn = sqlite3.connect(backup.storage_path)
            cursor = temp_conn.cursor()
            cursor.execute("PRAGMA quick_check;")
            res = cursor.fetchone()
            temp_conn.close()
            integrity_passed = (res and res[0] == "ok")
        except Exception:
            integrity_passed = False

        can_restore = checksum_match and integrity_passed

        preflight_id = f"pref-{uuid.uuid4().hex[:8]}"
        notes = "Preflight check passed cleanly." if can_restore else "Preflight verification failed integrity or checksum checks."

        return RestorePreflightReport(
            preflight_id=preflight_id,
            backup_id=backup_id,
            checksum_match=checksum_match,
            integrity_check_passed=integrity_passed,
            can_restore=can_restore,
            checked_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
            provenance=provenance or DisasterRecoveryProvenance(backup_id=backup_id),
        )

    def execute_human_authorized_restore(
        self,
        backup_id: str,
        target_db_path: str,
        *,
        executed_by: str,
        reason: str,
        provenance: DisasterRecoveryProvenance | None = None,
    ) -> RestoreOperationRecord:
        """Execute explicit human-authorized database restore from verified backup snapshot.

        Requirements:
        1. Non-empty audit reason required.
        2. Preflight verification MUST pass.
        3. Backup file MUST exist and match SHA-256.
        4. Operation is idempotent (compute_disaster_recovery_idempotency_key).
        5. Concurrency lock acquired (`phase29_recovery_locks`).
        6. Non-destructive safety: Existing target file is safely replaced only after preflight validation.
        """
        if not reason or not reason.strip():
            raise RestoreError("Explicit human audit reason is required for database restore execution.")

        # Check idempotency first
        idempotency_key = compute_disaster_recovery_idempotency_key(backup_id, executed_by, target_db_path)
        existing_op = self.repository.get_restore_operation_by_idempotency(idempotency_key)
        if existing_op:
            return existing_op

        # Acquire concurrency lock
        lock_key = f"restore:{backup_id}"
        acquired = self.repository.acquire_recovery_lock(lock_key, backup_id, executed_by)
        if not acquired:
            raise RestoreError(f"Concurrency lock active for backup '{backup_id}'. Restore execution rejected.")

        try:
            # Preflight inspection
            preflight = self.preflight_restore_check(backup_id, provenance)
            if not preflight.can_restore:
                raise RestoreError(f"Restore preflight failed for backup '{backup_id}': {preflight.notes}")

            backup = self.repository.get_backup_metadata(backup_id)
            if not backup:
                raise RestoreError(f"Backup record '{backup_id}' not found.")

            # Perform safe file restore
            dest_dir = os.path.dirname(target_db_path)
            if dest_dir:
                os.makedirs(dest_dir, exist_ok=True)

            shutil.copy2(backup.storage_path, target_db_path)

            # Verify target DB SHA-256 matches backup SHA-256
            target_sha256, _ = compute_file_sha256(target_db_path)
            if target_sha256 != backup.backup_sha256:
                raise RestoreError("Restore execution failed: Post-restore target database SHA-256 mismatch.")

            restore_id = f"rest-{uuid.uuid4().hex[:8]}"
            executed_at = datetime.now(timezone.utc).isoformat()
            audit_ref = f"AUDIT-PHASE29-RESTORE-{restore_id}"

            op = RestoreOperationRecord(
                restore_id=restore_id,
                backup_id=backup_id,
                target_db_path=target_db_path,
                executed_by=executed_by,
                executed_at=executed_at,
                reason=reason.strip(),
                idempotency_key=idempotency_key,
                audit_reference=audit_ref,
                status="RESTORE_VERIFIED",
                provenance=provenance or DisasterRecoveryProvenance(backup_id=backup_id, restore_id=restore_id),
            )

            self.repository.insert_restore_operation(op)
            return op
        finally:
            self.repository.release_recovery_lock(lock_key)
