"""Phase 29 — Disaster Recovery Repository.

Provides persistence and query access for:
- phase29_database_backups
- phase29_restore_operations
- phase29_recovery_locks

Zero business rules. Parametrized SQL queries only.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from core_model.capabilities.disaster_recovery_service import (
    BackupMetadataRecord,
    DisasterRecoveryProvenance,
    RestoreOperationRecord,
)


class DisasterRecoveryRepository:
    """SQLite repository for storing database backup metadata, restore operations, and recovery locks."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create additive tables phase29_database_backups, phase29_restore_operations, phase29_recovery_locks."""
        cursor = self.db.cursor()

        # Additive Table 1: phase29_database_backups
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phase29_database_backups (
                backup_id TEXT PRIMARY KEY,
                backup_type TEXT NOT NULL,
                source_db_sha256 TEXT NOT NULL,
                backup_sha256 TEXT NOT NULL,
                backup_size_bytes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                rpo_freshness_seconds REAL NOT NULL,
                is_verified INTEGER NOT NULL,
                created_by TEXT NOT NULL,
                provenance_json TEXT NOT NULL
            );
        """)

        # Additive Table 2: phase29_restore_operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phase29_restore_operations (
                restore_id TEXT PRIMARY KEY,
                backup_id TEXT NOT NULL,
                target_db_path TEXT NOT NULL,
                executed_by TEXT NOT NULL,
                executed_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                idempotency_key TEXT UNIQUE NOT NULL,
                audit_reference TEXT NOT NULL,
                status TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                FOREIGN KEY (backup_id) REFERENCES phase29_database_backups(backup_id)
            );
        """)

        # Additive Table 3: phase29_recovery_locks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phase29_recovery_locks (
                lock_key TEXT PRIMARY KEY,
                backup_id TEXT NOT NULL,
                acquired_by TEXT NOT NULL,
                acquired_at TEXT NOT NULL
            );
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_phase29_backups_created_at
            ON phase29_database_backups(created_at);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_phase29_restore_idempotency
            ON phase29_restore_operations(idempotency_key);
        """)

        self.db.commit()

    def insert_backup_metadata(self, b: BackupMetadataRecord) -> None:
        """Insert backup metadata record into phase29_database_backups."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            INSERT INTO phase29_database_backups (
                backup_id, backup_type, source_db_sha256, backup_sha256,
                backup_size_bytes, created_at, storage_path, rpo_freshness_seconds,
                is_verified, created_by, provenance_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                b.backup_id,
                b.backup_type,
                b.source_db_sha256,
                b.backup_sha256,
                b.backup_size_bytes,
                b.created_at,
                b.storage_path,
                b.rpo_freshness_seconds,
                1 if b.is_verified else 0,
                b.created_by,
                json.dumps(b.provenance.to_dict()),
            ),
        )
        self.db.commit()

    def get_backup_metadata(self, backup_id: str) -> BackupMetadataRecord | None:
        """Get backup metadata by ID."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT backup_id, backup_type, source_db_sha256, backup_sha256,
                   backup_size_bytes, created_at, storage_path, rpo_freshness_seconds,
                   is_verified, created_by, provenance_json
            FROM phase29_database_backups WHERE backup_id = ?;
            """,
            (backup_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        prov_dict = json.loads(row[10]) if row[10] else {}
        return BackupMetadataRecord(
            backup_id=row[0],
            backup_type=row[1],
            source_db_sha256=row[2],
            backup_sha256=row[3],
            backup_size_bytes=row[4],
            created_at=row[5],
            storage_path=row[6],
            rpo_freshness_seconds=row[7],
            is_verified=bool(row[8]),
            created_by=row[9],
            provenance=DisasterRecoveryProvenance.from_dict(prov_dict),
        )

    def list_backups(self, limit: int = 50) -> list[BackupMetadataRecord]:
        """List database backups ordered by creation timestamp descending."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT backup_id, backup_type, source_db_sha256, backup_sha256,
                   backup_size_bytes, created_at, storage_path, rpo_freshness_seconds,
                   is_verified, created_by, provenance_json
            FROM phase29_database_backups ORDER BY created_at DESC LIMIT ?;
            """,
            (limit,),
        )
        results = []
        for row in cursor.fetchall():
            prov_dict = json.loads(row[10]) if row[10] else {}
            results.append(
                BackupMetadataRecord(
                    backup_id=row[0],
                    backup_type=row[1],
                    source_db_sha256=row[2],
                    backup_sha256=row[3],
                    backup_size_bytes=row[4],
                    created_at=row[5],
                    storage_path=row[6],
                    rpo_freshness_seconds=row[7],
                    is_verified=bool(row[8]),
                    created_by=row[9],
                    provenance=DisasterRecoveryProvenance.from_dict(prov_dict),
                )
            )
        return results

    def update_backup_verification_status(self, backup_id: str, is_verified: bool) -> None:
        """Update is_verified status for a backup."""
        cursor = self.db.cursor()
        cursor.execute(
            "UPDATE phase29_database_backups SET is_verified = ? WHERE backup_id = ?;",
            (1 if is_verified else 0, backup_id),
        )
        self.db.commit()

    def insert_restore_operation(self, op: RestoreOperationRecord) -> None:
        """Insert restore operation audit record into phase29_restore_operations."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            INSERT INTO phase29_restore_operations (
                restore_id, backup_id, target_db_path, executed_by, executed_at,
                reason, idempotency_key, audit_reference, status, provenance_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                op.restore_id,
                op.backup_id,
                op.target_db_path,
                op.executed_by,
                op.executed_at,
                op.reason,
                op.idempotency_key,
                op.audit_reference,
                op.status,
                json.dumps(op.provenance.to_dict()),
            ),
        )
        self.db.commit()

    def get_restore_operation_by_idempotency(self, idempotency_key: str) -> RestoreOperationRecord | None:
        """Query restore operation by idempotency key."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT restore_id, backup_id, target_db_path, executed_by, executed_at,
                   reason, idempotency_key, audit_reference, status, provenance_json
            FROM phase29_restore_operations WHERE idempotency_key = ?;
            """,
            (idempotency_key,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        prov_dict = json.loads(row[9]) if row[9] else {}
        return RestoreOperationRecord(
            restore_id=row[0],
            backup_id=row[1],
            target_db_path=row[2],
            executed_by=row[3],
            executed_at=row[4],
            reason=row[5],
            idempotency_key=row[6],
            audit_reference=row[7],
            status=row[8],
            provenance=DisasterRecoveryProvenance.from_dict(prov_dict),
        )

    def acquire_recovery_lock(self, lock_key: str, backup_id: str, acquired_by: str) -> bool:
        """Acquire disaster recovery lock. Returns True if acquired, False if lock exists."""
        cursor = self.db.cursor()
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            cursor.execute(
                "INSERT INTO phase29_recovery_locks VALUES (?, ?, ?, ?);",
                (lock_key, backup_id, acquired_by, now_iso),
            )
            self.db.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def release_recovery_lock(self, lock_key: str) -> bool:
        """Release disaster recovery lock."""
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM phase29_recovery_locks WHERE lock_key = ?;", (lock_key,))
        self.db.commit()
        return cursor.rowcount > 0
