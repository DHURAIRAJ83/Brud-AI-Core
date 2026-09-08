"""Phase 22 — Controlled Ingestion & Dataset Export SQLite Repository.

Provides persistent storage, querying, operation log tracking, artifact versioning,
state updates, and aggregate metrics for Phase 22 controlled RAG ingestion and
dataset export operations.

CRITICAL INVARIANTS:
- All DDL uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
- Automated tests execute against isolated in-memory or temporary SQLite databases (:memory:).
- Zero external API calls, zero workers, zero subprocess execution.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Sequence

from core_model.capabilities.controlled_ingestion_service import (
    ControlledOperationRecord,
    ProvenanceChain,
)

CREATE_PHASE22_ARTIFACT_VERSIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase22_artifact_versions (
    artifact_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,
    artifact_version TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    source_gap_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    source_request_id TEXT NOT NULL,
    provenance_hash TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    checksum_sha256 TEXT NOT NULL,
    previous_version TEXT,
    rollback_reference_id TEXT,
    manifest_json TEXT NOT NULL
);
"""

CREATE_PHASE22_OPERATION_LOGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase22_operation_logs (
    operation_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL,
    candidate_type TEXT NOT NULL,
    status TEXT NOT NULL,
    dry_run_executed INTEGER NOT NULL,
    approved_by TEXT,
    approved_at TEXT,
    approval_notes TEXT,
    executed_by TEXT,
    executed_at TEXT,
    artifact_id TEXT,
    artifact_version TEXT,
    content_hash TEXT NOT NULL,
    provenance_hash TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    rollback_reference_id TEXT,
    provenance_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_PHASE22_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_phase22_art_type ON phase22_artifact_versions(artifact_type);",
    "CREATE INDEX IF NOT EXISTS idx_phase22_art_status ON phase22_artifact_versions(status);",
    "CREATE INDEX IF NOT EXISTS idx_phase22_op_candidate ON phase22_operation_logs(candidate_id);",
    "CREATE INDEX IF NOT EXISTS idx_phase22_op_status ON phase22_operation_logs(status);",
    "CREATE INDEX IF NOT EXISTS idx_phase22_op_idempotency ON phase22_operation_logs(idempotency_key);",
)


class ControlledIngestionRepository:
    """Repository for Phase 22 operation logs and versioned artifact registries."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self.conn:
            self.conn.execute(CREATE_PHASE22_ARTIFACT_VERSIONS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE22_OPERATION_LOGS_TABLE_SQL)
            for idx_sql in CREATE_PHASE22_INDEXES_SQL:
                self.conn.execute(idx_sql)

    # -----------------------------------------------------------------------
    # Operation Log Methods
    # -----------------------------------------------------------------------

    def insert_operation_record(self, record: ControlledOperationRecord) -> None:
        """Insert a ControlledOperationRecord."""
        sql = """
        INSERT INTO phase22_operation_logs (
            operation_id, candidate_id, candidate_type, status, dry_run_executed,
            approved_by, approved_at, approval_notes, executed_by, executed_at,
            artifact_id, artifact_version, content_hash, provenance_hash, idempotency_key,
            rollback_reference_id, provenance_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.operation_id,
                    record.candidate_id,
                    record.candidate_type,
                    record.status,
                    1 if record.dry_run_executed else 0,
                    record.approved_by,
                    record.approved_at,
                    record.approval_notes,
                    record.executed_by,
                    record.executed_at,
                    record.artifact_id,
                    record.artifact_version,
                    record.content_hash,
                    record.provenance_hash,
                    record.idempotency_key,
                    record.rollback_reference_id,
                    json.dumps(record.provenance.to_dict()),
                    record.created_at,
                    record.updated_at,
                ),
            )

    def get_operation_by_id(self, operation_id: str) -> ControlledOperationRecord | None:
        """Fetch an operation log record by ID."""
        sql = "SELECT * FROM phase22_operation_logs WHERE operation_id = ?;"
        cursor = self.conn.execute(sql, (operation_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_operation_record(row)

    def get_operation_by_idempotency_key(self, idempotency_key: str) -> ControlledOperationRecord | None:
        """Fetch an operation log record by idempotency key."""
        sql = "SELECT * FROM phase22_operation_logs WHERE idempotency_key = ?;"
        cursor = self.conn.execute(sql, (idempotency_key,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_operation_record(row)

    def update_operation_state(self, record: ControlledOperationRecord) -> None:
        """Update state fields on an operation record."""
        sql = """
        UPDATE phase22_operation_logs
        SET status = ?, approved_by = ?, approved_at = ?, approval_notes = ?,
            executed_by = ?, executed_at = ?, artifact_id = ?, artifact_version = ?,
            rollback_reference_id = ?, updated_at = ?
        WHERE operation_id = ?;
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.status,
                    record.approved_by,
                    record.approved_at,
                    record.approval_notes,
                    record.executed_by,
                    record.executed_at,
                    record.artifact_id,
                    record.artifact_version,
                    record.rollback_reference_id,
                    record.updated_at,
                    record.operation_id,
                ),
            )

    def list_operations(
        self,
        *,
        candidate_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[ControlledOperationRecord, ...]:
        """List operations with optional filtering."""
        query = "SELECT * FROM phase22_operation_logs"
        conditions: list[str] = []
        params: list[Any] = []

        if candidate_type:
            conditions.append("candidate_type = ?")
            params.append(candidate_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        return tuple(self._row_to_operation_record(row) for row in rows)

    # -----------------------------------------------------------------------
    # Artifact Version Registry Methods
    # -----------------------------------------------------------------------

    def insert_artifact_version(
        self,
        *,
        artifact_id: str,
        artifact_type: str,
        artifact_version: str,
        candidate_id: str,
        operation_id: str,
        source_gap_id: str,
        source_record_id: str,
        source_request_id: str,
        provenance_hash: str,
        content_hash: str,
        created_by: str,
        created_at: str,
        status: str,
        checksum_sha256: str,
        previous_version: str | None = None,
        rollback_reference_id: str | None = None,
        manifest: dict[str, Any] = None,
    ) -> None:
        """Insert an artifact version registry entry."""
        sql = """
        INSERT INTO phase22_artifact_versions (
            artifact_id, artifact_type, artifact_version, candidate_id, operation_id,
            source_gap_id, source_record_id, source_request_id, provenance_hash, content_hash,
            created_by, created_at, status, checksum_sha256, previous_version,
            rollback_reference_id, manifest_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    artifact_id,
                    artifact_type,
                    artifact_version,
                    candidate_id,
                    operation_id,
                    source_gap_id,
                    source_record_id,
                    source_request_id,
                    provenance_hash,
                    content_hash,
                    created_by,
                    created_at,
                    status,
                    checksum_sha256,
                    previous_version,
                    rollback_reference_id,
                    json.dumps(manifest or {}),
                ),
            )

    def get_artifact_version_by_id(self, artifact_id: str) -> dict[str, Any] | None:
        """Fetch an artifact version record by ID."""
        sql = "SELECT * FROM phase22_artifact_versions WHERE artifact_id = ?;"
        cursor = self.conn.execute(sql, (artifact_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)

    def update_artifact_status(self, artifact_id: str, status: str, rollback_ref: str | None = None) -> None:
        """Update artifact status (e.g. ROLLED_BACK)."""
        sql = "UPDATE phase22_artifact_versions SET status = ?, rollback_reference_id = ? WHERE artifact_id = ?;"
        with self.conn:
            self.conn.execute(sql, (status, rollback_ref, artifact_id))

    def aggregate_operation_metrics(self) -> dict[str, Any]:
        """Return aggregate operation counts."""
        cursor = self.conn.execute("SELECT status, count(*) as cnt FROM phase22_operation_logs GROUP BY status;")
        counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}
        return {
            "total_operations": sum(counts.values()),
            "status_counts": counts,
        }

    # -----------------------------------------------------------------------
    # Helper Row Converter
    # -----------------------------------------------------------------------

    def _row_to_operation_record(self, row: sqlite3.Row) -> ControlledOperationRecord:
        try:
            prov_dict = json.loads(row["provenance_json"])
            prov = ProvenanceChain(**prov_dict)
        except Exception:
            prov = ProvenanceChain(
                source_request_id="req-unknown",
                source_gap_id="gap-unknown",
                source_record_id="rec-unknown",
                candidate_id=row["candidate_id"],
                operation_id=row["operation_id"],
                artifact_id=row["artifact_id"],
                approved_by=row["approved_by"] or "system",
                approved_at=row["approved_at"] or "",
                gap_type="UNKNOWN",
                severity="low",
                candidate_type=row["candidate_type"],
            )

        return ControlledOperationRecord(
            operation_id=row["operation_id"],
            candidate_id=row["candidate_id"],
            candidate_type=row["candidate_type"],
            status=row["status"],
            dry_run_executed=bool(row["dry_run_executed"]),
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            approval_notes=row["approval_notes"],
            executed_by=row["executed_by"],
            executed_at=row["executed_at"],
            artifact_id=row["artifact_id"],
            artifact_version=row["artifact_version"],
            content_hash=row["content_hash"],
            provenance_hash=row["provenance_hash"],
            idempotency_key=row["idempotency_key"],
            rollback_reference_id=row["rollback_reference_id"],
            provenance=prov,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
