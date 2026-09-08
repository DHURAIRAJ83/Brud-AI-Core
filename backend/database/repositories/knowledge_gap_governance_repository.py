"""Phase 20 SQLite repository for Knowledge Gap Admin Inbox governance persistence.

Stores Knowledge Gap Records created from Phase 19 observations and tracks their
Phase 20 review, candidate classification, and human approval states.

CRITICAL SAFETY RULES:
- Additive table schema (CREATE TABLE IF NOT EXISTS).
- Zero deletion or truncation of existing production tables/records.
- Supports isolated in-memory or custom SQLite database connection paths for testing.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Mapping, Sequence
from uuid import uuid4

from core_model.capabilities.knowledge_gap_governance_service import (
    APPROVAL_APPROVED,
    APPROVAL_NOT_REQUESTED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    CANDIDATE_DATASET,
    CANDIDATE_NONE,
    CANDIDATE_RAG,
    KnowledgeGapRecord,
    STATUS_APPROVED,
    STATUS_CURATED,
    STATUS_DEFERRED,
    STATUS_IN_REVIEW,
    STATUS_NEW,
    STATUS_REJECTED,
)

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS knowledge_gap_records (
    record_id TEXT PRIMARY KEY,
    gap_id TEXT NOT NULL UNIQUE,
    request_id TEXT NOT NULL,
    detected_language TEXT NOT NULL,
    language_confidence REAL NOT NULL,
    normalized_intent TEXT NOT NULL,
    requested_capability_id TEXT,
    selected_capability_id TEXT,
    routing_confidence REAL NOT NULL,
    failure_classification TEXT NOT NULL,
    gap_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    clarification_required INTEGER NOT NULL,
    clarification_question TEXT,
    evidence_status TEXT NOT NULL,
    source_stage TEXT NOT NULL,
    safe_summary TEXT NOT NULL,
    sanitized_metadata_json TEXT NOT NULL,
    status TEXT NOT NULL,
    candidate_type TEXT NOT NULL,
    approval_state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    reviewer_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_kg_records_status ON knowledge_gap_records(status);
CREATE INDEX IF NOT EXISTS idx_kg_records_severity ON knowledge_gap_records(severity);
CREATE INDEX IF NOT EXISTS idx_kg_records_gap_type ON knowledge_gap_records(gap_type);
CREATE INDEX IF NOT EXISTS idx_kg_records_candidate_type ON knowledge_gap_records(candidate_type);
CREATE INDEX IF NOT EXISTS idx_kg_records_approval_state ON knowledge_gap_records(approval_state);
CREATE INDEX IF NOT EXISTS idx_kg_records_created_at ON knowledge_gap_records(created_at);
CREATE INDEX IF NOT EXISTS idx_kg_records_reviewed_by ON knowledge_gap_records(reviewed_by);
"""


def row_to_record(row: sqlite3.Row | Mapping[str, Any]) -> KnowledgeGapRecord:
    """Convert an SQLite row into a KnowledgeGapRecord instance."""
    metadata_json = row["sanitized_metadata_json"]
    metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else dict(metadata_json)

    return KnowledgeGapRecord(
        record_id=row["record_id"],
        gap_id=row["gap_id"],
        request_id=row["request_id"],
        detected_language=row["detected_language"],
        language_confidence=float(row["language_confidence"]),
        normalized_intent=row["normalized_intent"],
        requested_capability_id=row["requested_capability_id"],
        selected_capability_id=row["selected_capability_id"],
        routing_confidence=float(row["routing_confidence"]),
        failure_classification=row["failure_classification"],
        gap_type=row["gap_type"],
        severity=row["severity"],
        clarification_required=bool(row["clarification_required"]),
        clarification_question=row["clarification_question"],
        evidence_status=row["evidence_status"],
        source_stage=row["source_stage"],
        safe_summary=row["safe_summary"],
        sanitized_metadata=metadata,
        status=row["status"],
        candidate_type=row["candidate_type"],
        approval_state=row["approval_state"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        reviewed_at=row["reviewed_at"],
        reviewed_by=row["reviewed_by"],
        reviewer_notes=row["reviewer_notes"],
    )


class KnowledgeGapGovernanceRepository:
    """SQLite repository for Phase 20 Admin Knowledge Gap Inbox persistence."""

    def __init__(self, db_path_or_conn: str | sqlite3.Connection) -> None:
        if isinstance(db_path_or_conn, sqlite3.Connection):
            self.conn = db_path_or_conn
            self._external_conn = True
        else:
            self.db_path = db_path_or_conn
            self.conn = sqlite3.connect(db_path_or_conn)
            self._external_conn = False

        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        """Create table and indexes if they do not exist."""
        with self.conn:
            self.conn.executescript(_CREATE_TABLE_SQL)

    def close(self) -> None:
        """Close connection if managed internally."""
        if not self._external_conn and self.conn:
            self.conn.close()

    def insert_record(self, record: KnowledgeGapRecord) -> KnowledgeGapRecord:
        """Insert a new KnowledgeGapRecord into SQLite database."""
        sql = """
        INSERT INTO knowledge_gap_records (
            record_id, gap_id, request_id, detected_language, language_confidence,
            normalized_intent, requested_capability_id, selected_capability_id,
            routing_confidence, failure_classification, gap_type, severity,
            clarification_required, clarification_question, evidence_status,
            source_stage, safe_summary, sanitized_metadata_json, status,
            candidate_type, approval_state, created_at, updated_at,
            reviewed_at, reviewed_by, reviewer_notes
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.record_id,
                    record.gap_id,
                    record.request_id,
                    record.detected_language,
                    record.language_confidence,
                    record.normalized_intent,
                    record.requested_capability_id,
                    record.selected_capability_id,
                    record.routing_confidence,
                    record.failure_classification,
                    record.gap_type,
                    record.severity,
                    1 if record.clarification_required else 0,
                    record.clarification_question,
                    record.evidence_status,
                    record.source_stage,
                    record.safe_summary,
                    json.dumps(dict(record.sanitized_metadata)),
                    record.status,
                    record.candidate_type,
                    record.approval_state,
                    record.created_at,
                    record.updated_at,
                    record.reviewed_at,
                    record.reviewed_by,
                    record.reviewer_notes,
                ),
            )
        return record

    def get_record_by_id(self, record_id: str) -> KnowledgeGapRecord | None:
        """Retrieve a KnowledgeGapRecord by record_id."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM knowledge_gap_records WHERE record_id = ?", (record_id,))
        row = cursor.fetchone()
        return row_to_record(row) if row else None

    def get_record_by_gap_id(self, gap_id: str) -> KnowledgeGapRecord | None:
        """Retrieve a KnowledgeGapRecord by gap_id."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM knowledge_gap_records WHERE gap_id = ?", (gap_id,))
        row = cursor.fetchone()
        return row_to_record(row) if row else None

    def list_records(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        gap_type: str | None = None,
        candidate_type: str | None = None,
        approval_state: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[KnowledgeGapRecord]:
        """List KnowledgeGapRecords matching filters with pagination."""
        sql = "SELECT * FROM knowledge_gap_records WHERE 1=1"
        params: list[Any] = []

        if status:
            sql += " AND status = ?"
            params.append(status)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        if gap_type:
            sql += " AND gap_type = ?"
            params.append(gap_type)
        if candidate_type:
            sql += " AND candidate_type = ?"
            params.append(candidate_type)
        if approval_state:
            sql += " AND approval_state = ?"
            params.append(approval_state)

        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self.conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return tuple(row_to_record(row) for row in rows)

    def update_governance_state(self, record: KnowledgeGapRecord) -> KnowledgeGapRecord:
        """Update governance fields (status, candidate_type, approval_state, notes, timestamps)."""
        sql = """
        UPDATE knowledge_gap_records SET
            status = ?,
            candidate_type = ?,
            approval_state = ?,
            updated_at = ?,
            reviewed_at = ?,
            reviewed_by = ?,
            reviewer_notes = ?
        WHERE record_id = ?
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.status,
                    record.candidate_type,
                    record.approval_state,
                    record.updated_at,
                    record.reviewed_at,
                    record.reviewed_by,
                    record.reviewer_notes,
                    record.record_id,
                ),
            )
        return record

    def aggregate_inbox_metrics(self) -> dict[str, int]:
        """Compute aggregate Admin Inbox metrics."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM knowledge_gap_records")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT status, COUNT(*) FROM knowledge_gap_records GROUP BY status")
        status_counts = dict(cursor.fetchall())

        cursor.execute("SELECT severity, COUNT(*) FROM knowledge_gap_records GROUP BY severity")
        severity_counts = dict(cursor.fetchall())

        cursor.execute("SELECT candidate_type, COUNT(*) FROM knowledge_gap_records GROUP BY candidate_type")
        candidate_counts = dict(cursor.fetchall())

        cursor.execute("SELECT COUNT(*) FROM knowledge_gap_records WHERE gap_type = 'SECURITY_ADMIN_BOUNDARY'")
        critical_security_gaps = cursor.fetchone()[0]

        return {
            "total": total,
            "new": status_counts.get(STATUS_NEW, 0),
            "in_review": status_counts.get(STATUS_IN_REVIEW, 0),
            "curated": status_counts.get(STATUS_CURATED, 0),
            "approved": status_counts.get(STATUS_APPROVED, 0),
            "rejected": status_counts.get(STATUS_REJECTED, 0),
            "deferred": status_counts.get(STATUS_DEFERRED, 0),
            "critical_security_gaps": critical_security_gaps,
            "rag_candidates": candidate_counts.get(CANDIDATE_RAG, 0),
            "dataset_candidates": candidate_counts.get(CANDIDATE_DATASET, 0),
            "pending_approval": status_counts.get(STATUS_CURATED, 0),
        }


__all__ = ["KnowledgeGapGovernanceRepository", "row_to_record"]
