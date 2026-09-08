"""Phase 30 — Recovery Validation Repository.

Provides persistence and query access for:
- phase30_recovery_drills

Zero business rules. Parametrized SQL queries only.
"""

import json
import sqlite3
from typing import Any

from core_model.capabilities.recovery_validation_service import (
    RecoveryDrillRecord,
    RecoveryValidationProvenance,
)


class RecoveryValidationRepository:
    """SQLite repository for storing recovery drill records and metrics."""

    def __init__(self, db: sqlite3.Connection):
        self.db = db
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Create additive table phase30_recovery_drills."""
        cursor = self.db.cursor()

        # Additive Table: phase30_recovery_drills
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS phase30_recovery_drills (
                drill_id TEXT PRIMARY KEY,
                backup_id TEXT NOT NULL,
                drill_type TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                duration_seconds REAL NOT NULL,
                target_rto_seconds REAL NOT NULL,
                rto_status TEXT NOT NULL,
                backup_sha256 TEXT NOT NULL,
                restored_db_sha256 TEXT NOT NULL,
                integrity_status TEXT NOT NULL,
                schema_status TEXT NOT NULL,
                result TEXT NOT NULL,
                executed_by TEXT NOT NULL,
                audit_reference TEXT NOT NULL,
                idempotency_key TEXT UNIQUE NOT NULL,
                provenance_json TEXT NOT NULL
            );
        """)

        # Indexes
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_phase30_drills_started_at
            ON phase30_recovery_drills(started_at);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_phase30_drills_idempotency
            ON phase30_recovery_drills(idempotency_key);
        """)

        self.db.commit()

    def insert_recovery_drill(self, d: RecoveryDrillRecord) -> None:
        """Insert a recovery drill record into phase30_recovery_drills."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            INSERT INTO phase30_recovery_drills (
                drill_id, backup_id, drill_type, started_at, completed_at,
                duration_seconds, target_rto_seconds, rto_status, backup_sha256,
                restored_db_sha256, integrity_status, schema_status, result,
                executed_by, audit_reference, idempotency_key, provenance_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                d.drill_id,
                d.backup_id,
                d.drill_type,
                d.started_at,
                d.completed_at,
                d.duration_seconds,
                d.target_rto_seconds,
                d.rto_status,
                d.backup_sha256,
                d.restored_db_sha256,
                d.integrity_status,
                d.schema_status,
                d.result,
                d.executed_by,
                d.audit_reference,
                d.idempotency_key,
                json.dumps(d.provenance.to_dict()),
            ),
        )
        self.db.commit()

    def get_recovery_drill_by_id(self, drill_id: str) -> RecoveryDrillRecord | None:
        """Get recovery drill record by drill ID."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT drill_id, backup_id, drill_type, started_at, completed_at,
                   duration_seconds, target_rto_seconds, rto_status, backup_sha256,
                   restored_db_sha256, integrity_status, schema_status, result,
                   executed_by, audit_reference, idempotency_key, provenance_json
            FROM phase30_recovery_drills WHERE drill_id = ?;
            """,
            (drill_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        prov_dict = json.loads(row[16]) if row[16] else {}
        return RecoveryDrillRecord(
            drill_id=row[0],
            backup_id=row[1],
            drill_type=row[2],
            started_at=row[3],
            completed_at=row[4],
            duration_seconds=row[5],
            target_rto_seconds=row[6],
            rto_status=row[7],
            backup_sha256=row[8],
            restored_db_sha256=row[9],
            integrity_status=row[10],
            schema_status=row[11],
            result=row[12],
            executed_by=row[13],
            audit_reference=row[14],
            idempotency_key=row[15],
            provenance=RecoveryValidationProvenance.from_dict(prov_dict),
        )

    def get_recovery_drill_by_idempotency(self, idempotency_key: str) -> RecoveryDrillRecord | None:
        """Query recovery drill by idempotency key."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT drill_id, backup_id, drill_type, started_at, completed_at,
                   duration_seconds, target_rto_seconds, rto_status, backup_sha256,
                   restored_db_sha256, integrity_status, schema_status, result,
                   executed_by, audit_reference, idempotency_key, provenance_json
            FROM phase30_recovery_drills WHERE idempotency_key = ?;
            """,
            (idempotency_key,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        prov_dict = json.loads(row[16]) if row[16] else {}
        return RecoveryDrillRecord(
            drill_id=row[0],
            backup_id=row[1],
            drill_type=row[2],
            started_at=row[3],
            completed_at=row[4],
            duration_seconds=row[5],
            target_rto_seconds=row[6],
            rto_status=row[7],
            backup_sha256=row[8],
            restored_db_sha256=row[9],
            integrity_status=row[10],
            schema_status=row[11],
            result=row[12],
            executed_by=row[13],
            audit_reference=row[14],
            idempotency_key=row[15],
            provenance=RecoveryValidationProvenance.from_dict(prov_dict),
        )

    def list_recovery_drills(self, limit: int = 50) -> list[RecoveryDrillRecord]:
        """List recovery drill records ordered by started_at descending."""
        cursor = self.db.cursor()
        cursor.execute(
            """
            SELECT drill_id, backup_id, drill_type, started_at, completed_at,
                   duration_seconds, target_rto_seconds, rto_status, backup_sha256,
                   restored_db_sha256, integrity_status, schema_status, result,
                   executed_by, audit_reference, idempotency_key, provenance_json
            FROM phase30_recovery_drills ORDER BY started_at DESC LIMIT ?;
            """,
            (limit,),
        )
        results = []
        for row in cursor.fetchall():
            prov_dict = json.loads(row[16]) if row[16] else {}
            results.append(
                RecoveryDrillRecord(
                    drill_id=row[0],
                    backup_id=row[1],
                    drill_type=row[2],
                    started_at=row[3],
                    completed_at=row[4],
                    duration_seconds=row[5],
                    target_rto_seconds=row[6],
                    rto_status=row[7],
                    backup_sha256=row[8],
                    restored_db_sha256=row[9],
                    integrity_status=row[10],
                    schema_status=row[11],
                    result=row[12],
                    executed_by=row[13],
                    audit_reference=row[14],
                    idempotency_key=row[15],
                    provenance=RecoveryValidationProvenance.from_dict(prov_dict),
                )
            )
        return results

    def get_latest_recovery_drill(self) -> RecoveryDrillRecord | None:
        """Get the single most recent recovery drill record."""
        drills = self.list_recovery_drills(limit=1)
        return drills[0] if drills else None
