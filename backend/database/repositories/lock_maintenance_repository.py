"""Phase 28 — Lock Maintenance Repository.

Provides persistence and query access for:
- phase24_release_locks
- phase25_deployment_locks
- phase26_health_locks
- phase28_lock_cleanup_operations (ADDITIVE TABLE)

Zero business rules. Parametrized SQL queries only.
"""

import json
import sqlite3
from typing import Any

from core_model.capabilities.lock_maintenance_service import (
    LockCleanupOperation,
    LockMaintenanceProvenance,
)


class LockMaintenanceRepository:
    """SQLite repository for inspecting concurrency locks and storing cleanup audit records."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create additive table phase28_lock_cleanup_operations if it does not exist."""
        cursor = self.db.cursor()

        # Additive Table: phase28_lock_cleanup_operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phase28_lock_cleanup_operations (
                cleanup_id TEXT PRIMARY KEY,
                lock_table TEXT NOT NULL,
                lock_key TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                released_by TEXT NOT NULL,
                released_at TEXT NOT NULL,
                reason TEXT NOT NULL,
                idempotency_key TEXT UNIQUE NOT NULL,
                audit_reference TEXT NOT NULL,
                provenance_json TEXT NOT NULL
            );
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_phase28_cleanup_lock_table_key
            ON phase28_lock_cleanup_operations(lock_table, lock_key);
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_phase28_cleanup_idempotency
            ON phase28_lock_cleanup_operations(idempotency_key);
        """)

        self.db.commit()

    def query_all_active_locks(self) -> list[dict[str, Any]]:
        """Fetch all active lock records from Phase 24, 25, and 26 lock tables."""
        cursor = self.db.cursor()
        locks: list[dict[str, Any]] = []

        # Phase 24 Release Locks
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='phase24_release_locks';
        """)
        if cursor.fetchone():
            cursor.execute("""
                SELECT lock_key, release_id, acquired_by, acquired_at FROM phase24_release_locks;
            """)
            for row in cursor.fetchall():
                locks.append({
                    "lock_table": "phase24_release_locks",
                    "lock_key": row[0],
                    "resource_id": row[1] or "",
                    "acquired_by": row[2] or "",
                    "acquired_at": row[3] or "",
                    "phase_origin": "Phase 24 Release Management",
                })

        # Phase 25 Deployment Locks
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='phase25_deployment_locks';
        """)
        if cursor.fetchone():
            cursor.execute("""
                SELECT lock_key, release_id, acquired_by, acquired_at FROM phase25_deployment_locks;
            """)
            for row in cursor.fetchall():
                locks.append({
                    "lock_table": "phase25_deployment_locks",
                    "lock_key": row[0],
                    "resource_id": row[1] or "",
                    "acquired_by": row[2] or "",
                    "acquired_at": row[3] or "",
                    "phase_origin": "Phase 25 Deployment Gate",
                })

        # Phase 26 Health Locks
        cursor.execute("""
            SELECT name FROM sqlite_master WHERE type='table' AND name='phase26_health_locks';
        """)
        if cursor.fetchone():
            cursor.execute("""
                SELECT lock_key, incident_id, acquired_by, acquired_at FROM phase26_health_locks;
            """)
            for row in cursor.fetchall():
                locks.append({
                    "lock_table": "phase26_health_locks",
                    "lock_key": row[0],
                    "resource_id": row[1] or "",
                    "acquired_by": row[2] or "",
                    "acquired_at": row[3] or "",
                    "phase_origin": "Phase 26 Production Observability",
                })

        return locks

    def get_lock(self, lock_table: str, lock_key: str) -> dict[str, Any] | None:
        """Get a single lock record by table and key."""
        allowed_tables = {
            "phase24_release_locks": ("release_id", "Phase 24 Release Management"),
            "phase25_deployment_locks": ("release_id", "Phase 25 Deployment Gate"),
            "phase26_health_locks": ("incident_id", "Phase 26 Production Observability"),
        }
        if lock_table not in allowed_tables:
            return None

        res_col, origin = allowed_tables[lock_table]
        cursor = self.db.cursor()

        cursor.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (lock_table,),
        )
        if not cursor.fetchone():
            return None

        query = f"SELECT lock_key, {res_col}, acquired_by, acquired_at FROM {lock_table} WHERE lock_key = ?;"
        cursor.execute(query, (lock_key,))
        row = cursor.fetchone()
        if not row:
            return None

        return {
            "lock_table": lock_table,
            "lock_key": row[0],
            "resource_id": row[1] or "",
            "acquired_by": row[2] or "",
            "acquired_at": row[3] or "",
            "phase_origin": origin,
        }

    def delete_lock(self, lock_table: str, lock_key: str) -> bool:
        """Delete an explicitly approved stale lock record from the specified lock table."""
        allowed_tables = {"phase24_release_locks", "phase25_deployment_locks", "phase26_health_locks"}
        if lock_table not in allowed_tables:
            return False

        cursor = self.db.cursor()
        query = f"DELETE FROM {lock_table} WHERE lock_key = ?;"
        cursor.execute(query, (lock_key,))
        self.db.commit()
        return cursor.rowcount > 0

    def insert_cleanup_operation(self, op: LockCleanupOperation) -> None:
        """Insert a lock cleanup audit operation into phase28_lock_cleanup_operations."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            INSERT INTO phase28_lock_cleanup_operations (
                cleanup_id, lock_table, lock_key, resource_id, released_by,
                released_at, reason, idempotency_key, audit_reference, provenance_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                op.cleanup_id,
                op.lock_table,
                op.lock_key,
                op.resource_id,
                op.released_by,
                op.released_at,
                op.reason,
                op.idempotency_key,
                op.audit_reference,
                json.dumps(op.provenance.to_dict()),
            ),
        )
        self.db.commit()

    def get_cleanup_operation_by_idempotency(self, idempotency_key: str) -> LockCleanupOperation | None:
        """Query lock cleanup operation by idempotency key."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT cleanup_id, lock_table, lock_key, resource_id, released_by,
                   released_at, reason, idempotency_key, audit_reference, provenance_json
            FROM phase28_lock_cleanup_operations WHERE idempotency_key = ?;
            """,
            (idempotency_key,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        prov_dict = json.loads(row[9]) if row[9] else {}
        return LockCleanupOperation(
            cleanup_id=row[0],
            lock_table=row[1],
            lock_key=row[2],
            resource_id=row[3],
            released_by=row[4],
            released_at=row[5],
            reason=row[6],
            idempotency_key=row[7],
            audit_reference=row[8],
            provenance=LockMaintenanceProvenance.from_dict(prov_dict),
        )
