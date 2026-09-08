"""Phase 23 — Evaluation & Quality Validation SQLite Repository.

Provides persistent storage, querying, version comparisons, metric results,
human review decisions, state updates, and aggregate metrics for Phase 23 evaluation operations.

CRITICAL INVARIANTS:
- All DDL uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
- Automated unit and integration tests execute against isolated in-memory or temporary SQLite databases (:memory:).
- Zero external API calls, zero workers, zero subprocess execution.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Sequence

from core_model.capabilities.evaluation_service import (
    EvaluationMetric,
    EvaluationProvenance,
    EvaluationRecord,
    EvaluationReview,
    VersionComparison,
)

CREATE_PHASE23_EVALUATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase23_evaluation_records (
    evaluation_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    artifact_version TEXT NOT NULL,
    status TEXT NOT NULL,
    overall_score REAL NOT NULL,
    notes TEXT,
    provenance_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

CREATE_PHASE23_METRICS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase23_metric_results (
    metric_id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL,
    metric_version TEXT NOT NULL,
    name TEXT NOT NULL,
    value REAL NOT NULL,
    calculation_method TEXT NOT NULL,
    input_artifact_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL,
    evidence TEXT,
    FOREIGN KEY(evaluation_id) REFERENCES phase23_evaluation_records(evaluation_id)
);
"""

CREATE_PHASE23_COMPARISONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase23_version_comparisons (
    comparison_id TEXT PRIMARY KEY,
    artifact_type TEXT NOT NULL,
    version_a TEXT NOT NULL,
    version_b TEXT NOT NULL,
    added_content_count INTEGER NOT NULL,
    removed_content_count INTEGER NOT NULL,
    modified_content_count INTEGER NOT NULL,
    quality_delta REAL NOT NULL,
    regression_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    provenance_hash TEXT NOT NULL,
    notes TEXT
);
"""

CREATE_PHASE23_REVIEWS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase23_review_decisions (
    review_id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewed_by TEXT NOT NULL,
    reviewed_at TEXT NOT NULL,
    reviewer_notes TEXT,
    provenance_json TEXT NOT NULL,
    FOREIGN KEY(evaluation_id) REFERENCES phase23_evaluation_records(evaluation_id)
);
"""

CREATE_PHASE23_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_phase23_eval_art ON phase23_evaluation_records(artifact_id);",
    "CREATE INDEX IF NOT EXISTS idx_phase23_eval_status ON phase23_evaluation_records(status);",
    "CREATE INDEX IF NOT EXISTS idx_phase23_met_eval ON phase23_metric_results(evaluation_id);",
    "CREATE INDEX IF NOT EXISTS idx_phase23_comp_versions ON phase23_version_comparisons(version_a, version_b);",
    "CREATE INDEX IF NOT EXISTS idx_phase23_rev_eval ON phase23_review_decisions(evaluation_id);",
)


class EvaluationRepository:
    """Repository for Phase 23 evaluation records, metric results, version comparisons, and review decisions."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self.conn:
            self.conn.execute(CREATE_PHASE23_EVALUATIONS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE23_METRICS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE23_COMPARISONS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE23_REVIEWS_TABLE_SQL)
            for idx_sql in CREATE_PHASE23_INDEXES_SQL:
                self.conn.execute(idx_sql)

    # -----------------------------------------------------------------------
    # Evaluation Record Methods
    # -----------------------------------------------------------------------

    def insert_evaluation_record(self, record: EvaluationRecord) -> None:
        """Insert an evaluation record and its associated metrics."""
        sql_eval = """
        INSERT INTO phase23_evaluation_records (
            evaluation_id, artifact_id, artifact_type, artifact_version, status,
            overall_score, notes, provenance_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        sql_metric = """
        INSERT INTO phase23_metric_results (
            metric_id, evaluation_id, metric_version, name, value,
            calculation_method, input_artifact_id, timestamp, status, evidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql_eval,
                (
                    record.evaluation_id,
                    record.artifact_id,
                    record.artifact_type,
                    record.artifact_version,
                    record.status,
                    record.overall_score,
                    record.notes,
                    json.dumps(record.provenance.to_dict()),
                    record.created_at,
                    record.updated_at,
                ),
            )
            for m in record.metrics:
                self.conn.execute(
                    sql_metric,
                    (
                        m.metric_id,
                        record.evaluation_id,
                        m.metric_version,
                        m.name,
                        m.value,
                        m.calculation_method,
                        m.input_artifact_id,
                        m.timestamp,
                        m.status,
                        m.evidence,
                    ),
                )

    def get_evaluation_by_id(self, evaluation_id: str) -> EvaluationRecord | None:
        """Fetch an evaluation record by ID with metrics."""
        cursor = self.conn.execute(
            "SELECT * FROM phase23_evaluation_records WHERE evaluation_id = ?;", (evaluation_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Fetch metrics
        m_cursor = self.conn.execute(
            "SELECT * FROM phase23_metric_results WHERE evaluation_id = ?;", (evaluation_id,)
        )
        m_rows = m_cursor.fetchall()
        metrics = tuple(
            EvaluationMetric(
                metric_id=m["metric_id"],
                metric_version=m["metric_version"],
                name=m["name"],
                value=m["value"],
                calculation_method=m["calculation_method"],
                input_artifact_id=m["input_artifact_id"],
                timestamp=m["timestamp"],
                status=m["status"],
                evidence=m["evidence"],
            )
            for m in m_rows
        )

        prov_dict = json.loads(row["provenance_json"])
        prov = EvaluationProvenance(**prov_dict)

        return EvaluationRecord(
            evaluation_id=row["evaluation_id"],
            artifact_id=row["artifact_id"],
            artifact_type=row["artifact_type"],
            artifact_version=row["artifact_version"],
            status=row["status"],
            overall_score=row["overall_score"],
            metrics=metrics,
            provenance=prov,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            notes=row["notes"],
        )

    def update_evaluation_state(self, record: EvaluationRecord) -> None:
        """Update evaluation status and provenance."""
        sql = """
        UPDATE phase23_evaluation_records
        SET status = ?, overall_score = ?, notes = ?, provenance_json = ?, updated_at = ?
        WHERE evaluation_id = ?;
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    record.status,
                    record.overall_score,
                    record.notes,
                    json.dumps(record.provenance.to_dict()),
                    record.updated_at,
                    record.evaluation_id,
                ),
            )

    def list_evaluations(
        self,
        *,
        artifact_id: str | None = None,
        artifact_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[EvaluationRecord, ...]:
        """List evaluation records with optional filtering."""
        query = "SELECT evaluation_id FROM phase23_evaluation_records"
        conditions: list[str] = []
        params: list[Any] = []

        if artifact_id:
            conditions.append("artifact_id = ?")
            params.append(artifact_id)
        if artifact_type:
            conditions.append("artifact_type = ?")
            params.append(artifact_type)
        if status:
            conditions.append("status = ?")
            params.append(status)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?;"
        params.extend([limit, offset])

        cursor = self.conn.execute(query, params)
        rows = cursor.fetchall()
        evals = []
        for r in rows:
            rec = self.get_evaluation_by_id(r["evaluation_id"])
            if rec:
                evals.append(rec)
        return tuple(evals)

    # -----------------------------------------------------------------------
    # Version Comparison Methods
    # -----------------------------------------------------------------------

    def insert_version_comparison(self, comp: VersionComparison) -> None:
        """Insert a VersionComparison record."""
        sql = """
        INSERT INTO phase23_version_comparisons (
            comparison_id, artifact_type, version_a, version_b, added_content_count,
            removed_content_count, modified_content_count, quality_delta, regression_status,
            created_at, provenance_hash, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    comp.comparison_id,
                    comp.artifact_type,
                    comp.version_a,
                    comp.version_b,
                    comp.added_content_count,
                    comp.removed_content_count,
                    comp.modified_content_count,
                    comp.quality_delta,
                    comp.regression_status,
                    comp.created_at,
                    comp.provenance_hash,
                    comp.notes,
                ),
            )

    def get_comparison(self, version_a: str, version_b: str) -> VersionComparison | None:
        """Fetch a version comparison entry by versions."""
        sql = "SELECT * FROM phase23_version_comparisons WHERE version_a = ? AND version_b = ?;"
        cursor = self.conn.execute(sql, (version_a, version_b))
        row = cursor.fetchone()
        if not row:
            return None
        return VersionComparison(
            comparison_id=row["comparison_id"],
            artifact_type=row["artifact_type"],
            version_a=row["version_a"],
            version_b=row["version_b"],
            added_content_count=row["added_content_count"],
            removed_content_count=row["removed_content_count"],
            modified_content_count=row["modified_content_count"],
            quality_delta=row["quality_delta"],
            regression_status=row["regression_status"],
            created_at=row["created_at"],
            provenance_hash=row["provenance_hash"],
            notes=row["notes"],
        )

    # -----------------------------------------------------------------------
    # Review Decision Methods
    # -----------------------------------------------------------------------

    def insert_review_decision(self, review: EvaluationReview) -> None:
        """Insert an EvaluationReview decision."""
        sql = """
        INSERT INTO phase23_review_decisions (
            review_id, evaluation_id, decision, reviewed_by, reviewed_at, reviewer_notes, provenance_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?);
        """
        prov_json = json.dumps(review.provenance.to_dict()) if review.provenance else "{}"
        with self.conn:
            self.conn.execute(
                sql,
                (
                    review.review_id,
                    review.evaluation_id,
                    review.decision,
                    review.reviewed_by,
                    review.reviewed_at,
                    review.reviewer_notes,
                    prov_json,
                ),
            )

    def get_reviews_for_evaluation(self, evaluation_id: str) -> tuple[EvaluationReview, ...]:
        """Fetch review decision entries for an evaluation."""
        sql = "SELECT * FROM phase23_review_decisions WHERE evaluation_id = ? ORDER BY reviewed_at DESC;"
        cursor = self.conn.execute(sql, (evaluation_id,))
        rows = cursor.fetchall()
        revs = []
        for r in rows:
            p_dict = json.loads(r["provenance_json"]) if r["provenance_json"] else None
            prov = EvaluationProvenance(**p_dict) if p_dict else None
            revs.append(
                EvaluationReview(
                    review_id=r["review_id"],
                    evaluation_id=r["evaluation_id"],
                    decision=r["decision"],
                    reviewed_by=r["reviewed_by"],
                    reviewed_at=r["reviewed_at"],
                    reviewer_notes=r["reviewer_notes"],
                    provenance=prov,
                )
            )
        return tuple(revs)

    def aggregate_metrics(self) -> dict[str, Any]:
        """Return aggregate metrics on evaluations and review decisions."""
        cursor = self.conn.execute("SELECT status, count(*) as cnt FROM phase23_evaluation_records GROUP BY status;")
        counts = {row["status"]: row["cnt"] for row in cursor.fetchall()}
        return {
            "total_evaluations": sum(counts.values()),
            "status_counts": counts,
        }
