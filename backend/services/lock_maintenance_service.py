"""Phase 28 — Lock Maintenance Service.

Coordinates lock inspection, stale status determination, RBAC identity checks,
human-governed release authorization, idempotency verification, and audit logging.
"""

import sqlite3
import uuid
from datetime import datetime, timezone

from backend.database.repositories.lock_maintenance_repository import LockMaintenanceRepository
from core_model.capabilities.lock_maintenance_service import (
    InvalidLockError,
    LockCleanupOperation,
    LockInspectionReport,
    LockMaintenanceProvenance,
    LockReleaseError,
    StaleLockRecord,
    compute_lock_age_seconds,
    compute_lock_cleanup_idempotency_key,
    is_lock_stale,
)


class LockMaintenanceService:
    """Backend service for Phase 28 stale-lock governance and operations hardening."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self.repository = LockMaintenanceRepository(db)

    def inspect_locks(
        self,
        stale_threshold_seconds: float = 3600.0,
        current_time_iso: str | None = None,
        provenance: LockMaintenanceProvenance | None = None,
    ) -> LockInspectionReport:
        """Inspect all active locks across Phase 24, 25, and 26 tables and calculate stale status.

        Inspection ONLY observes and reports. Zero lock mutation or deletion is performed.
        """
        raw_locks = self.repository.query_all_active_locks()
        records: list[StaleLockRecord] = []
        stale_count = 0
        fresh_count = 0

        now_iso = current_time_iso or datetime.now(timezone.utc).isoformat()

        for lock in raw_locks:
            try:
                age_sec = compute_lock_age_seconds(lock["acquired_at"], now_iso)
                stale = is_lock_stale(age_sec, stale_threshold_seconds)
            except InvalidLockError:
                age_sec = 0.0
                stale = False

            if stale:
                stale_count += 1
            else:
                fresh_count += 1

            records.append(
                StaleLockRecord(
                    lock_table=lock["lock_table"],
                    lock_key=lock["lock_key"],
                    resource_id=lock["resource_id"],
                    acquired_by=lock["acquired_by"],
                    acquired_at=lock["acquired_at"],
                    age_seconds=age_sec,
                    lock_ttl_seconds=stale_threshold_seconds,
                    is_stale=stale,
                    phase_origin=lock["phase_origin"],
                )
            )

        insp_id = f"lock-insp-{uuid.uuid4().hex[:8]}"
        return LockInspectionReport(
            inspection_id=insp_id,
            inspected_at=now_iso,
            total_locks_count=len(records),
            stale_locks_count=stale_count,
            fresh_locks_count=fresh_count,
            locks=records,
            provenance=provenance or LockMaintenanceProvenance(lock_maintenance_id=insp_id),
        )

    def get_lock_detail(
        self,
        lock_table: str,
        lock_key: str,
        stale_threshold_seconds: float = 3600.0,
        current_time_iso: str | None = None,
    ) -> StaleLockRecord | None:
        """Inspect detail of a single lock record."""
        lock = self.repository.get_lock(lock_table, lock_key)
        if not lock:
            return None

        now_iso = current_time_iso or datetime.now(timezone.utc).isoformat()
        try:
            age_sec = compute_lock_age_seconds(lock["acquired_at"], now_iso)
            stale = is_lock_stale(age_sec, stale_threshold_seconds)
        except InvalidLockError:
            age_sec = 0.0
            stale = False

        return StaleLockRecord(
            lock_table=lock["lock_table"],
            lock_key=lock["lock_key"],
            resource_id=lock["resource_id"],
            acquired_by=lock["acquired_by"],
            acquired_at=lock["acquired_at"],
            age_seconds=age_sec,
            lock_ttl_seconds=stale_threshold_seconds,
            is_stale=stale,
            phase_origin=lock["phase_origin"],
        )

    def release_stale_lock(
        self,
        lock_table: str,
        lock_key: str,
        *,
        released_by: str,
        reason: str,
        stale_threshold_seconds: float = 3600.0,
        provenance: LockMaintenanceProvenance | None = None,
    ) -> LockCleanupOperation:
        """Explicit human-authorized release of a verified stale lock record.

        Requirements:
        1. Non-empty audit reason required.
        2. Lock MUST exist and be verified stale (age_seconds > lock_ttl_seconds).
        3. Fresh locks MUST be protected (release rejected).
        4. Operation is idempotent (compute_lock_cleanup_idempotency_key).
        5. Zero automatic deployment, rollback, or process restart.
        """
        # Validate audit reason
        if not reason or not reason.strip():
            raise LockReleaseError("Explicit human audit reason is required for lock release.")

        # Check idempotency first
        idempotency_key = compute_lock_cleanup_idempotency_key(lock_table, lock_key, released_by)
        existing_op = self.repository.get_cleanup_operation_by_idempotency(idempotency_key)
        if existing_op:
            return existing_op

        # Retrieve lock detail
        lock_detail = self.get_lock_detail(lock_table, lock_key, stale_threshold_seconds)
        if not lock_detail:
            raise InvalidLockError(f"Lock '{lock_key}' in table '{lock_table}' not found.")

        # Verify lock is stale (FRESH LOCK PROTECTION)
        if not lock_detail.is_stale:
            raise LockReleaseError(
                f"Lock '{lock_key}' in table '{lock_table}' is FRESH "
                f"(age: {lock_detail.age_seconds:.1f}s <= TTL: {stale_threshold_seconds:.1f}s). "
                f"Release rejected."
            )

        # Execute explicit lock deletion
        deleted = self.repository.delete_lock(lock_table, lock_key)
        if not deleted:
            raise LockReleaseError(f"Failed to release lock '{lock_key}' from '{lock_table}'.")

        cleanup_id = f"lock-clean-{uuid.uuid4().hex[:8]}"
        released_at = datetime.now(timezone.utc).isoformat()
        audit_ref = f"AUDIT-PHASE28-RELEASE-{cleanup_id}"

        op = LockCleanupOperation(
            cleanup_id=cleanup_id,
            lock_table=lock_table,
            lock_key=lock_key,
            resource_id=lock_detail.resource_id,
            released_by=released_by,
            released_at=released_at,
            reason=reason.strip(),
            idempotency_key=idempotency_key,
            audit_reference=audit_ref,
            provenance=provenance or LockMaintenanceProvenance(lock_maintenance_id=cleanup_id),
        )

        self.repository.insert_cleanup_operation(op)
        return op
