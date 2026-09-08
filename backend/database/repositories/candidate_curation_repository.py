"""Phase 21 — Candidate Curation SQLite Repository.

Provides persistent storage, querying, state update, and metrics aggregation for staged
RAG and Dataset candidate records.

CRITICAL INVARIANTS:
- All DDL operations use CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
- Tests execute against isolated in-memory or temporary SQLite databases (:memory:).
- Zero external API calls, zero workers, zero subprocess execution.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Sequence

from core_model.capabilities.candidate_curation_service import (
    DATASET_STATUS_READY_FOR_EXPORT,
    DUPLICATE_EXACT,
    RAG_STATUS_READY_FOR_INGESTION,
    STAGING_STATUS_APPROVED,
    STAGING_STATUS_DEFERRED,
    STAGING_STATUS_DRAFT,
    STAGING_STATUS_PENDING_REVIEW,
    STAGING_STATUS_REJECTED,
    STAGING_STATUS_VALIDATED,
    CandidateProvenance,
    DatasetCandidateStagingRecord,
    RAGCandidateStagingRecord,
)

CREATE_RAG_STAGING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS rag_candidate_staging_records (
    candidate_id TEXT PRIMARY KEY,
    provenance_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    source_gap_id TEXT NOT NULL,
    source_request_id TEXT NOT NULL,
    source_gap_type TEXT NOT NULL,
    source_severity TEXT NOT NULL,
    source_summary TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    source_stage TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    provenance_hash TEXT NOT NULL,
    candidate_version TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    duplicate_status TEXT NOT NULL,
    conflict_status TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    reviewer_notes TEXT,
    sanitized_metadata_json TEXT NOT NULL
);
"""

CREATE_DATASET_STAGING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS dataset_candidate_staging_records (
    candidate_id TEXT PRIMARY KEY,
    provenance_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    source_gap_id TEXT NOT NULL,
    source_request_id TEXT NOT NULL,
    source_gap_type TEXT NOT NULL,
    source_severity TEXT NOT NULL,
    source_summary TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    source_stage TEXT NOT NULL,
    input_context TEXT NOT NULL,
    proposed_output TEXT NOT NULL,
    language TEXT NOT NULL,
    domain_topic TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    provenance_hash TEXT NOT NULL,
    candidate_version TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    duplicate_status TEXT NOT NULL,
    conflict_status TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    reviewer_notes TEXT,
    sanitized_metadata_json TEXT NOT NULL
);
"""

CREATE_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_rag_staging_status ON rag_candidate_staging_records(status);",
    "CREATE INDEX IF NOT EXISTS idx_rag_staging_dup_status ON rag_candidate_staging_records(duplicate_status);",
    "CREATE INDEX IF NOT EXISTS idx_rag_staging_conflict_status ON rag_candidate_staging_records(conflict_status);",
    "CREATE INDEX IF NOT EXISTS idx_rag_staging_content_hash ON rag_candidate_staging_records(content_hash);",
    "CREATE INDEX IF NOT EXISTS idx_rag_staging_created_at ON rag_candidate_staging_records(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_ds_staging_status ON dataset_candidate_staging_records(status);",
    "CREATE INDEX IF NOT EXISTS idx_ds_staging_dup_status ON dataset_candidate_staging_records(duplicate_status);",
    "CREATE INDEX IF NOT EXISTS idx_ds_staging_conflict_status ON dataset_candidate_staging_records(conflict_status);",
    "CREATE INDEX IF NOT EXISTS idx_ds_staging_content_hash ON dataset_candidate_staging_records(content_hash);",
    "CREATE INDEX IF NOT EXISTS idx_ds_staging_created_at ON dataset_candidate_staging_records(created_at);",
)


class CandidateCurationRepository:
    """Repository for managing RAG and Dataset candidate staging tables."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self.conn:
            self.conn.execute(CREATE_RAG_STAGING_TABLE_SQL)
            self.conn.execute(CREATE_DATASET_STAGING_TABLE_SQL)
            for idx_sql in CREATE_INDEXES_SQL:
                self.conn.execute(idx_sql)

    # -----------------------------------------------------------------------
    # RAG Candidate Methods
    # -----------------------------------------------------------------------

    def insert_rag_candidate(self, record: RAGCandidateStagingRecord) -> None:
        """Insert a RAGCandidateStagingRecord."""
        sql = """
        INSERT INTO rag_candidate_staging_records (
            candidate_id, provenance_id, source_record_id, source_gap_id, source_request_id,
            source_gap_type, source_severity, source_summary, approved_by, approved_at, source_stage,
            title, content, content_hash, provenance_hash, candidate_version, validation_status,
            duplicate_status, conflict_status, status, created_at, updated_at, reviewed_at,
            reviewed_by, reviewer_notes, sanitized_metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.candidate_id,
                    record.provenance.provenance_id,
                    record.provenance.source_record_id,
                    record.provenance.source_gap_id,
                    record.provenance.source_request_id,
                    record.provenance.source_gap_type,
                    record.provenance.source_severity,
                    record.provenance.source_summary,
                    record.provenance.approved_by,
                    record.provenance.approved_at,
                    record.provenance.source_stage,
                    record.title,
                    record.content,
                    record.content_hash,
                    record.provenance_hash,
                    record.candidate_version,
                    record.validation_status,
                    record.duplicate_status,
                    record.conflict_status,
                    record.status,
                    record.created_at,
                    record.updated_at,
                    record.reviewed_at,
                    record.reviewed_by,
                    record.reviewer_notes,
                    json.dumps(record.sanitized_metadata),
                ),
            )

    def get_rag_candidate_by_id(self, candidate_id: str) -> RAGCandidateStagingRecord | None:
        """Fetch a RAG candidate by ID."""
        sql = "SELECT * FROM rag_candidate_staging_records WHERE candidate_id = ?;"
        cursor = self.conn.execute(sql, (candidate_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_rag_record(row)

    def list_rag_candidates(
        self,
        *,
        status: str | None = None,
        duplicate_status: str | None = None,
        conflict_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[RAGCandidateStagingRecord, ...]:
        """List RAG candidates with optional filtering."""
        query = "SELECT * FROM rag_candidate_staging_records"
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if duplicate_status:
            conditions.append("duplicate_status = ?")
            params.append(duplicate_status)
        if conflict_status:
            conditions.append("conflict_status = ?")
            params.append(conflict_status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        return tuple(self._row_to_rag_record(row) for row in rows)

    def update_rag_candidate_state(self, record: RAGCandidateStagingRecord) -> None:
        """Update governance fields on a RAG candidate."""
        sql = """
        UPDATE rag_candidate_staging_records
        SET status = ?, reviewed_at = ?, reviewed_by = ?, reviewer_notes = ?, updated_at = ?
        WHERE candidate_id = ?;
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.status,
                    record.reviewed_at,
                    record.reviewed_by,
                    record.reviewer_notes,
                    record.updated_at,
                    record.candidate_id,
                ),
            )

    # -----------------------------------------------------------------------
    # Dataset Candidate Methods
    # -----------------------------------------------------------------------

    def insert_dataset_candidate(self, record: DatasetCandidateStagingRecord) -> None:
        """Insert a DatasetCandidateStagingRecord."""
        sql = """
        INSERT INTO dataset_candidate_staging_records (
            candidate_id, provenance_id, source_record_id, source_gap_id, source_request_id,
            source_gap_type, source_severity, source_summary, approved_by, approved_at, source_stage,
            input_context, proposed_output, language, domain_topic, content_hash, provenance_hash,
            candidate_version, validation_status, duplicate_status, conflict_status, status,
            created_at, updated_at, reviewed_at, reviewed_by, reviewer_notes, sanitized_metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.candidate_id,
                    record.provenance.provenance_id,
                    record.provenance.source_record_id,
                    record.provenance.source_gap_id,
                    record.provenance.source_request_id,
                    record.provenance.source_gap_type,
                    record.provenance.source_severity,
                    record.provenance.source_summary,
                    record.provenance.approved_by,
                    record.provenance.approved_at,
                    record.provenance.source_stage,
                    record.input_context,
                    record.proposed_output,
                    record.language,
                    record.domain_topic,
                    record.content_hash,
                    record.provenance_hash,
                    record.candidate_version,
                    record.validation_status,
                    record.duplicate_status,
                    record.conflict_status,
                    record.status,
                    record.created_at,
                    record.updated_at,
                    record.reviewed_at,
                    record.reviewed_by,
                    record.reviewer_notes,
                    json.dumps(record.sanitized_metadata),
                ),
            )

    def get_dataset_candidate_by_id(self, candidate_id: str) -> DatasetCandidateStagingRecord | None:
        """Fetch a Dataset candidate by ID."""
        sql = "SELECT * FROM dataset_candidate_staging_records WHERE candidate_id = ?;"
        cursor = self.conn.execute(sql, (candidate_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return self._row_to_dataset_record(row)

    def list_dataset_candidates(
        self,
        *,
        status: str | None = None,
        duplicate_status: str | None = None,
        conflict_status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[DatasetCandidateStagingRecord, ...]:
        """List Dataset candidates with optional filtering."""
        query = "SELECT * FROM dataset_candidate_staging_records"
        conditions: list[str] = []
        params: list[Any] = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if duplicate_status:
            conditions.append("duplicate_status = ?")
            params.append(duplicate_status)
        if conflict_status:
            conditions.append("conflict_status = ?")
            params.append(conflict_status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        return tuple(self._row_to_dataset_record(row) for row in rows)

    def update_dataset_candidate_state(self, record: DatasetCandidateStagingRecord) -> None:
        """Update governance fields on a Dataset candidate."""
        sql = """
        UPDATE dataset_candidate_staging_records
        SET status = ?, reviewed_at = ?, reviewed_by = ?, reviewer_notes = ?, updated_at = ?
        WHERE candidate_id = ?;
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.status,
                    record.reviewed_at,
                    record.reviewed_by,
                    record.reviewer_notes,
                    record.updated_at,
                    record.candidate_id,
                ),
            )

    # -----------------------------------------------------------------------
    # Aggregate Staging Metrics
    # -----------------------------------------------------------------------

    def aggregate_staging_metrics(self) -> dict[str, Any]:
        """Return aggregate counts across RAG and Dataset staging tables."""
        rag_cursor = self.conn.execute("SELECT status, count(*) as cnt FROM rag_candidate_staging_records GROUP BY status;")
        rag_counts = {row["status"]: row["cnt"] for row in rag_cursor.fetchall()}

        ds_cursor = self.conn.execute("SELECT status, count(*) as cnt FROM dataset_candidate_staging_records GROUP BY status;")
        ds_counts = {row["status"]: row["cnt"] for row in ds_cursor.fetchall()}

        rag_total = sum(rag_counts.values())
        ds_total = sum(ds_counts.values())

        return {
            "total_staged_candidates": rag_total + ds_total,
            "rag_candidates_total": rag_total,
            "dataset_candidates_total": ds_total,
            "rag_ready_for_ingestion": rag_counts.get(RAG_STATUS_READY_FOR_INGESTION, 0),
            "dataset_ready_for_export": ds_counts.get(DATASET_STATUS_READY_FOR_EXPORT, 0),
            "rag_pending_review": rag_counts.get(STAGING_STATUS_PENDING_REVIEW, 0),
            "dataset_pending_review": ds_counts.get(STAGING_STATUS_PENDING_REVIEW, 0),
        }

    # -----------------------------------------------------------------------
    # Row Converter Helpers
    # -----------------------------------------------------------------------

    def _row_to_rag_record(self, row: sqlite3.Row) -> RAGCandidateStagingRecord:
        prov = CandidateProvenance(
            provenance_id=row["provenance_id"],
            source_record_id=row["source_record_id"],
            source_gap_id=row["source_gap_id"],
            source_request_id=row["source_request_id"],
            source_gap_type=row["source_gap_type"],
            source_severity=row["source_severity"],
            source_summary=row["source_summary"],
            candidate_type="RAG_CANDIDATE",
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            source_stage=row["source_stage"],
        )
        try:
            meta = json.loads(row["sanitized_metadata_json"])
        except Exception:
            meta = {}

        return RAGCandidateStagingRecord(
            candidate_id=row["candidate_id"],
            provenance=prov,
            title=row["title"],
            content=row["content"],
            content_hash=row["content_hash"],
            provenance_hash=row["provenance_hash"],
            candidate_version=row["candidate_version"],
            validation_status=row["validation_status"],
            duplicate_status=row["duplicate_status"],
            conflict_status=row["conflict_status"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            reviewed_at=row["reviewed_at"],
            reviewed_by=row["reviewed_by"],
            reviewer_notes=row["reviewer_notes"],
            sanitized_metadata=meta,
        )

    def _row_to_dataset_record(self, row: sqlite3.Row) -> DatasetCandidateStagingRecord:
        prov = CandidateProvenance(
            provenance_id=row["provenance_id"],
            source_record_id=row["source_record_id"],
            source_gap_id=row["source_gap_id"],
            source_request_id=row["source_request_id"],
            source_gap_type=row["source_gap_type"],
            source_severity=row["source_severity"],
            source_summary=row["source_summary"],
            candidate_type="DATASET_CANDIDATE",
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            source_stage=row["source_stage"],
        )
        try:
            meta = json.loads(row["sanitized_metadata_json"])
        except Exception:
            meta = {}

        return DatasetCandidateStagingRecord(
            candidate_id=row["candidate_id"],
            provenance=prov,
            input_context=row["input_context"],
            proposed_output=row["proposed_output"],
            language=row["language"],
            domain_topic=row["domain_topic"],
            content_hash=row["content_hash"],
            provenance_hash=row["provenance_hash"],
            candidate_version=row["candidate_version"],
            validation_status=row["validation_status"],
            duplicate_status=row["duplicate_status"],
            conflict_status=row["conflict_status"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            reviewed_at=row["reviewed_at"],
            reviewed_by=row["reviewed_by"],
            reviewer_notes=row["reviewer_notes"],
            sanitized_metadata=meta,
        )
