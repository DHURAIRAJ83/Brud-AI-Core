"""Phase 24 — Release Management, Promotion & Rollback SQLite Repository.

Provides persistent storage, querying, release candidates, approvals, promotion operations,
rollback operations, atomic active version pointers, state updates, and aggregate metrics.

CRITICAL INVARIANTS:
- All DDL uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
- Automated unit and integration tests execute against isolated in-memory or temporary SQLite databases (:memory:).
- Zero external API calls, zero workers, zero subprocess execution.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Sequence

from core_model.capabilities.release_management_service import (
    PromotionOperation,
    ReleaseApproval,
    ReleaseCandidate,
    ReleaseProvenance,
    RollbackOperation,
)

CREATE_PHASE24_CANDIDATES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase24_release_candidates (
    release_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_version TEXT NOT NULL,
    evaluation_id TEXT NOT NULL,
    evaluation_status TEXT NOT NULL,
    release_status TEXT NOT NULL,
    release_version TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    provenance_hash TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    notes TEXT
);
"""

CREATE_PHASE24_APPROVALS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase24_release_approvals (
    approval_id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewer_notes TEXT,
    approval_hash TEXT NOT NULL,
    FOREIGN KEY(release_id) REFERENCES phase24_release_candidates(release_id)
);
"""

CREATE_PHASE24_PROMOTIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase24_promotion_operations (
    operation_id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL,
    source_version TEXT NOT NULL,
    target_version TEXT NOT NULL,
    previous_active_version TEXT,
    promotion_status TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    audit_reference TEXT NOT NULL,
    FOREIGN KEY(release_id) REFERENCES phase24_release_candidates(release_id)
);
"""

CREATE_PHASE24_ROLLBACKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase24_rollback_operations (
    rollback_id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL,
    from_version TEXT NOT NULL,
    to_version TEXT NOT NULL,
    rollback_status TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    executed_at TEXT NOT NULL,
    reason TEXT NOT NULL,
    audit_reference TEXT NOT NULL,
    FOREIGN KEY(release_id) REFERENCES phase24_release_candidates(release_id)
);
"""

CREATE_PHASE24_ACTIVE_POINTERS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase24_active_version_pointers (
    artifact_type TEXT NOT NULL,
    space_or_target_id TEXT NOT NULL,
    active_release_id TEXT NOT NULL,
    active_release_version TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(artifact_type, space_or_target_id)
);
"""

CREATE_PHASE24_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_phase24_rel_art ON phase24_release_candidates(artifact_id);",
    "CREATE INDEX IF NOT EXISTS idx_phase24_rel_status ON phase24_release_candidates(release_status);",
    "CREATE INDEX IF NOT EXISTS idx_phase24_app_rel ON phase24_release_approvals(release_id);",
    "CREATE INDEX IF NOT EXISTS idx_phase24_prom_rel ON phase24_promotion_operations(release_id);",
    "CREATE INDEX IF NOT EXISTS idx_phase24_prom_key ON phase24_promotion_operations(idempotency_key);",
    "CREATE INDEX IF NOT EXISTS idx_phase24_rb_rel ON phase24_rollback_operations(release_id);",
)


class ReleaseRepository:
    """Repository for Phase 24 release candidates, approvals, promotions, rollbacks, and active version pointers."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self.conn:
            self.conn.execute(CREATE_PHASE24_CANDIDATES_TABLE_SQL)
            self.conn.execute(CREATE_PHASE24_APPROVALS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE24_PROMOTIONS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE24_ROLLBACKS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE24_ACTIVE_POINTERS_TABLE_SQL)
            for idx_sql in CREATE_PHASE24_INDEXES_SQL:
                self.conn.execute(idx_sql)

    # -----------------------------------------------------------------------
    # Release Candidate Methods
    # -----------------------------------------------------------------------

    def insert_release_candidate(self, candidate: ReleaseCandidate) -> None:
        """Insert a new ReleaseCandidate entry."""
        sql = """
        INSERT INTO phase24_release_candidates (
            release_id, artifact_id, artifact_type, artifact_version, evaluation_id,
            evaluation_status, release_status, release_version, content_hash,
            provenance_hash, created_by, created_at, provenance_json, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    candidate.release_id,
                    candidate.artifact_id,
                    candidate.artifact_type,
                    candidate.artifact_version,
                    candidate.evaluation_id,
                    candidate.evaluation_status,
                    candidate.release_status,
                    candidate.release_version,
                    candidate.content_hash,
                    candidate.provenance_hash,
                    candidate.created_by,
                    candidate.created_at,
                    json.dumps(candidate.provenance.to_dict()),
                    candidate.notes,
                ),
            )

    def get_release_by_id(self, release_id: str) -> ReleaseCandidate | None:
        """Fetch a ReleaseCandidate by release ID."""
        sql = "SELECT * FROM phase24_release_candidates WHERE release_id = ?;"
        cursor = self.conn.execute(sql, (release_id,))
        row = cursor.fetchone()
        if not row:
            return None

        prov_dict = json.loads(row["provenance_json"])
        prov = ReleaseProvenance(**prov_dict)

        return ReleaseCandidate(
            release_id=row["release_id"],
            artifact_id=row["artifact_id"],
            artifact_type=row["artifact_type"],
            artifact_version=row["artifact_version"],
            evaluation_id=row["evaluation_id"],
            evaluation_status=row["evaluation_status"],
            release_status=row["release_status"],
            release_version=row["release_version"],
            content_hash=row["content_hash"],
            provenance_hash=row["provenance_hash"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            provenance=prov,
            notes=row["notes"],
        )

    def update_release_status(self, candidate: ReleaseCandidate) -> None:
        """Update release candidate status and notes."""
        sql = """
        UPDATE phase24_release_candidates
        SET release_status = ?, notes = ?, provenance_json = ?
        WHERE release_id = ?;
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    candidate.release_status,
                    candidate.notes,
                    json.dumps(candidate.provenance.to_dict()),
                    candidate.release_id,
                ),
            )

    def list_releases(
        self,
        *,
        artifact_id: str | None = None,
        artifact_type: str | None = None,
        release_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[ReleaseCandidate, ...]:
        """List release candidates with optional filtering."""
        query = "SELECT release_id FROM phase24_release_candidates"
        conditions: list[str] = []
        params: list[Any] = []

        if artifact_id:
            conditions.append("artifact_id = ?")
            params.append(artifact_id)
        if artifact_type:
            conditions.append("artifact_type = ?")
            params.append(artifact_type)
        if release_status:
            conditions.append("release_status = ?")
            params.append(release_status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        rels = []
        for r in rows:
            rel = self.get_release_by_id(r["release_id"])
            if rel:
                rels.append(rel)
        return tuple(rels)

    # -----------------------------------------------------------------------
    # Approval, Promotion & Rollback Methods
    # -----------------------------------------------------------------------

    def insert_release_approval(self, approval: ReleaseApproval) -> None:
        """Insert a ReleaseApproval entry."""
        sql = """
        INSERT INTO phase24_release_approvals (
            approval_id, release_id, approved_by, approved_at, decision, reviewer_notes, approval_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    approval.approval_id,
                    approval.release_id,
                    approval.approved_by,
                    approval.approved_at,
                    approval.decision,
                    approval.reviewer_notes,
                    approval.approval_hash,
                ),
            )

    def insert_promotion_operation(self, op: PromotionOperation) -> None:
        """Insert a PromotionOperation entry."""
        sql = """
        INSERT INTO phase24_promotion_operations (
            operation_id, release_id, source_version, target_version, previous_active_version,
            promotion_status, idempotency_key, approved_by, approved_at, executed_at,
            verification_status, audit_reference
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    op.operation_id,
                    op.release_id,
                    op.source_version,
                    op.target_version,
                    op.previous_active_version,
                    op.promotion_status,
                    op.idempotency_key,
                    op.approved_by,
                    op.approved_at,
                    op.executed_at,
                    op.verification_status,
                    op.audit_reference,
                ),
            )

    def get_promotion_by_idempotency_key(self, idempotency_key: str) -> PromotionOperation | None:
        """Fetch a promotion operation by its idempotency key."""
        sql = "SELECT * FROM phase24_promotion_operations WHERE idempotency_key = ?;"
        cursor = self.conn.execute(sql, (idempotency_key,))
        row = cursor.fetchone()
        if not row:
            return None
        return PromotionOperation(
            operation_id=row["operation_id"],
            release_id=row["release_id"],
            source_version=row["source_version"],
            target_version=row["target_version"],
            previous_active_version=row["previous_active_version"],
            promotion_status=row["promotion_status"],
            idempotency_key=row["idempotency_key"],
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            executed_at=row["executed_at"],
            verification_status=row["verification_status"],
            audit_reference=row["audit_reference"],
        )

    def insert_rollback_operation(self, op: RollbackOperation) -> None:
        """Insert a RollbackOperation entry."""
        sql = """
        INSERT INTO phase24_rollback_operations (
            rollback_id, release_id, from_version, to_version, rollback_status,
            approved_by, approved_at, executed_at, reason, audit_reference
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    op.rollback_id,
                    op.release_id,
                    op.from_version,
                    op.to_version,
                    op.rollback_status,
                    op.approved_by,
                    op.approved_at,
                    op.executed_at,
                    op.reason,
                    op.audit_reference,
                ),
            )

    # -----------------------------------------------------------------------
    # Active Version Pointer Methods
    # -----------------------------------------------------------------------

    def update_active_version_pointer(
        self,
        artifact_type: str,
        space_or_target_id: str,
        active_release_id: str,
        active_release_version: str,
        updated_by: str,
        updated_at: str,
    ) -> None:
        """Atomically insert or update the active version pointer for a target space."""
        sql = """
        INSERT INTO phase24_active_version_pointers (
            artifact_type, space_or_target_id, active_release_id, active_release_version, updated_by, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(artifact_type, space_or_target_id) DO UPDATE SET
            active_release_id = excluded.active_release_id,
            active_release_version = excluded.active_release_version,
            updated_by = excluded.updated_by,
            updated_at = excluded.updated_at;
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    artifact_type,
                    space_or_target_id,
                    active_release_id,
                    active_release_version,
                    updated_by,
                    updated_at,
                ),
            )

    def get_active_version_pointer(
        self, artifact_type: str, space_or_target_id: str = "default"
    ) -> dict[str, Any] | None:
        """Fetch the current active version pointer for a target space."""
        sql = "SELECT * FROM phase24_active_version_pointers WHERE artifact_type = ? AND space_or_target_id = ?;"
        cursor = self.conn.execute(sql, (artifact_type, space_or_target_id))
        row = cursor.fetchone()
        if not row:
            return None
        return dict(row)

    def aggregate_metrics(self) -> dict[str, Any]:
        """Return aggregate metrics on release candidates, promotions, and active versions."""
        cursor = self.conn.execute("SELECT release_status, count(*) as cnt FROM phase24_release_candidates GROUP BY release_status;")
        counts = {row["release_status"]: row["cnt"] for row in cursor.fetchall()}
        return {
            "total_releases": sum(counts.values()),
            "status_counts": counts,
        }
