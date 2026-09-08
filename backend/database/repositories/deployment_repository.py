"""Phase 25 — Deployment Readiness, Gate & Operational Safety SQLite Repository.

Provides persistent storage, readiness reports, readiness check items, human deployment approvals,
deployment operations, deployment rollbacks, and concurrency deployment locks.

CRITICAL INVARIANTS:
- All DDL uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS.
- Automated unit and integration tests execute against isolated in-memory or temporary SQLite databases (:memory:).
- Zero external API calls, zero workers, zero subprocess execution.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any, Sequence

from core_model.capabilities.deployment_readiness_service import (
    DeploymentApproval,
    DeploymentOperation,
    DeploymentProvenance,
    DeploymentReadinessReport,
    DeploymentRollback,
    ReadinessCheck,
)

CREATE_PHASE25_REPORTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase25_readiness_reports (
    readiness_id TEXT PRIMARY KEY,
    release_id TEXT NOT NULL,
    active_version TEXT NOT NULL,
    target_environment TEXT NOT NULL,
    readiness_status TEXT NOT NULL,
    overall_score REAL NOT NULL,
    blockers_json TEXT NOT NULL,
    warnings_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    configuration_hash TEXT NOT NULL,
    dependency_hash TEXT NOT NULL,
    provenance_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

CREATE_PHASE25_CHECKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase25_readiness_checks (
    check_id TEXT PRIMARY KEY,
    readiness_id TEXT NOT NULL,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    expected TEXT NOT NULL,
    actual TEXT NOT NULL,
    evidence TEXT NOT NULL,
    FOREIGN KEY(readiness_id) REFERENCES phase25_readiness_reports(readiness_id)
);
"""

CREATE_PHASE25_APPROVALS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase25_deployment_approvals (
    approval_id TEXT PRIMARY KEY,
    readiness_id TEXT NOT NULL,
    release_id TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    decision TEXT NOT NULL,
    reviewer_notes TEXT,
    approval_hash TEXT NOT NULL,
    FOREIGN KEY(readiness_id) REFERENCES phase25_readiness_reports(readiness_id)
);
"""

CREATE_PHASE25_OPERATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase25_deployment_operations (
    deployment_id TEXT PRIMARY KEY,
    readiness_id TEXT NOT NULL,
    release_id TEXT NOT NULL,
    target_environment TEXT NOT NULL,
    previous_version TEXT,
    target_version TEXT NOT NULL,
    deployment_status TEXT NOT NULL,
    idempotency_key TEXT UNIQUE NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    audit_reference TEXT NOT NULL,
    FOREIGN KEY(readiness_id) REFERENCES phase25_readiness_reports(readiness_id)
);
"""

CREATE_PHASE25_ROLLBACKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase25_deployment_rollbacks (
    rollback_id TEXT PRIMARY KEY,
    deployment_id TEXT NOT NULL,
    from_version TEXT NOT NULL,
    to_version TEXT NOT NULL,
    reason TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    approved_at TEXT NOT NULL,
    rollback_status TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    audit_reference TEXT NOT NULL,
    FOREIGN KEY(deployment_id) REFERENCES phase25_deployment_operations(deployment_id)
);
"""

CREATE_PHASE25_LOCKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS phase25_deployment_locks (
    release_id TEXT PRIMARY KEY,
    deployment_id TEXT NOT NULL,
    locked_by TEXT NOT NULL,
    locked_at TEXT NOT NULL
);
"""

CREATE_PHASE25_INDEXES_SQL = (
    "CREATE INDEX IF NOT EXISTS idx_phase25_rep_rel ON phase25_readiness_reports(release_id);",
    "CREATE INDEX IF NOT EXISTS idx_phase25_rep_status ON phase25_readiness_reports(readiness_status);",
    "CREATE INDEX IF NOT EXISTS idx_phase25_chk_rep ON phase25_readiness_checks(readiness_id);",
    "CREATE INDEX IF NOT EXISTS idx_phase25_app_rep ON phase25_deployment_approvals(readiness_id);",
    "CREATE INDEX IF NOT EXISTS idx_phase25_op_key ON phase25_deployment_operations(idempotency_key);",
    "CREATE INDEX IF NOT EXISTS idx_phase25_rb_dep ON phase25_deployment_rollbacks(deployment_id);",
)


class DeploymentRepository:
    """Repository for Phase 25 readiness reports, approvals, operations, rollbacks, and locks."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self._initialize_schema()

    def _initialize_schema(self) -> None:
        """Create tables and indexes if they do not exist."""
        with self.conn:
            self.conn.execute(CREATE_PHASE25_REPORTS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE25_CHECKS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE25_APPROVALS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE25_OPERATIONS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE25_ROLLBACKS_TABLE_SQL)
            self.conn.execute(CREATE_PHASE25_LOCKS_TABLE_SQL)
            for idx_sql in CREATE_PHASE25_INDEXES_SQL:
                self.conn.execute(idx_sql)

    # -----------------------------------------------------------------------
    # Readiness Report Methods
    # -----------------------------------------------------------------------

    def insert_readiness_report(self, report: DeploymentReadinessReport) -> None:
        """Insert a DeploymentReadinessReport and its check items."""
        sql_rep = """
        INSERT INTO phase25_readiness_reports (
            readiness_id, release_id, active_version, target_environment, readiness_status,
            overall_score, blockers_json, warnings_json, content_hash, configuration_hash,
            dependency_hash, provenance_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        sql_chk = """
        INSERT INTO phase25_readiness_checks (
            check_id, readiness_id, category, name, status, severity, expected, actual, evidence
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql_rep,
                (
                    report.readiness_id,
                    report.release_id,
                    report.active_version,
                    report.target_environment,
                    report.readiness_status,
                    report.overall_score,
                    json.dumps(list(report.blockers)),
                    json.dumps(list(report.warnings)),
                    report.content_hash,
                    report.configuration_hash,
                    report.dependency_hash,
                    json.dumps(report.provenance.to_dict()),
                    report.created_at,
                ),
            )
            for chk in report.checks:
                self.conn.execute(
                    sql_chk,
                    (
                        chk.check_id,
                        report.readiness_id,
                        chk.category,
                        chk.name,
                        chk.status,
                        chk.severity,
                        chk.expected,
                        chk.actual,
                        chk.evidence,
                    ),
                )

    def get_readiness_report_by_id(self, readiness_id: str) -> DeploymentReadinessReport | None:
        """Fetch a DeploymentReadinessReport by readiness ID."""
        sql_rep = "SELECT * FROM phase25_readiness_reports WHERE readiness_id = ?;"
        cursor = self.conn.execute(sql_rep, (readiness_id,))
        row = cursor.fetchone()
        if not row:
            return None

        sql_chk = "SELECT * FROM phase25_readiness_checks WHERE readiness_id = ?;"
        chk_rows = self.conn.execute(sql_chk, (readiness_id,)).fetchall()
        checks = [
            ReadinessCheck(
                check_id=r["check_id"],
                category=r["category"],
                name=r["name"],
                status=r["status"],
                severity=r["severity"],
                expected=r["expected"],
                actual=r["actual"],
                evidence=r["evidence"],
            )
            for r in chk_rows
        ]

        prov_dict = json.loads(row["provenance_json"])
        prov = DeploymentProvenance(**prov_dict)

        return DeploymentReadinessReport(
            readiness_id=row["readiness_id"],
            release_id=row["release_id"],
            active_version=row["active_version"],
            target_environment=row["target_environment"],
            readiness_status=row["readiness_status"],
            checks=tuple(checks),
            overall_score=row["overall_score"],
            blockers=tuple(json.loads(row["blockers_json"])),
            warnings=tuple(json.loads(row["warnings_json"])),
            content_hash=row["content_hash"],
            configuration_hash=row["configuration_hash"],
            dependency_hash=row["dependency_hash"],
            provenance=prov,
            created_at=row["created_at"],
        )

    def update_readiness_status(self, report: DeploymentReadinessReport) -> None:
        """Update readiness report status and provenance."""
        sql = """
        UPDATE phase25_readiness_reports
        SET readiness_status = ?, provenance_json = ?
        WHERE readiness_id = ?;
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    report.readiness_status,
                    json.dumps(report.provenance.to_dict()),
                    report.readiness_id,
                ),
            )

    # -----------------------------------------------------------------------
    # Deployment Concurrency Lock Methods
    # -----------------------------------------------------------------------

    def acquire_deployment_lock(self, release_id: str, deployment_id: str, locked_by: str) -> bool:
        """Acquire an atomic deployment lock for a release ID."""
        sql = "INSERT INTO phase25_deployment_locks (release_id, deployment_id, locked_by, locked_at) VALUES (?, ?, ?, ?);"
        now_str = opacity = datetime.now(UTC).isoformat()
        try:
            with self.conn:
                self.conn.execute(sql, (release_id, deployment_id, locked_by, now_str))
            return True
        except sqlite3.IntegrityError:
            return False

    def release_deployment_lock(self, release_id: str, deployment_id: str) -> None:
        """Release an active deployment lock."""
        sql = "DELETE FROM phase25_deployment_locks WHERE release_id = ? AND deployment_id = ?;"
        with self.conn:
            self.conn.execute(sql, (release_id, deployment_id))

    # -----------------------------------------------------------------------
    # Approval, Operations & Rollbacks Methods
    # -----------------------------------------------------------------------

    def insert_deployment_approval(self, approval: DeploymentApproval) -> None:
        """Insert a DeploymentApproval entry."""
        sql = """
        INSERT INTO phase25_deployment_approvals (
            approval_id, readiness_id, release_id, approved_by, approved_at, decision, reviewer_notes, approval_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    approval.approval_id,
                    approval.readiness_id,
                    approval.release_id,
                    approval.approved_by,
                    approval.approved_at,
                    approval.decision,
                    approval.reviewer_notes,
                    approval.approval_hash,
                ),
            )

    def insert_deployment_operation(self, op: DeploymentOperation) -> None:
        """Insert a DeploymentOperation entry."""
        sql = """
        INSERT INTO phase25_deployment_operations (
            deployment_id, readiness_id, release_id, target_environment, previous_version,
            target_version, deployment_status, idempotency_key, approved_by, approved_at,
            started_at, completed_at, verification_status, audit_reference
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    op.deployment_id,
                    op.readiness_id,
                    op.release_id,
                    op.target_environment,
                    op.previous_version,
                    op.target_version,
                    op.deployment_status,
                    op.idempotency_key,
                    op.approved_by,
                    op.approved_at,
                    op.started_at,
                    op.completed_at,
                    op.verification_status,
                    op.audit_reference,
                ),
            )

    def get_deployment_by_idempotency_key(self, idempotency_key: str) -> DeploymentOperation | None:
        """Fetch a deployment operation by its idempotency key."""
        sql = "SELECT * FROM phase25_deployment_operations WHERE idempotency_key = ?;"
        cursor = self.conn.execute(sql, (idempotency_key,))
        row = cursor.fetchone()
        if not row:
            return None
        return DeploymentOperation(
            deployment_id=row["deployment_id"],
            readiness_id=row["readiness_id"],
            release_id=row["release_id"],
            target_environment=row["target_environment"],
            previous_version=row["previous_version"],
            target_version=row["target_version"],
            deployment_status=row["deployment_status"],
            idempotency_key=row["idempotency_key"],
            approved_by=row["approved_by"],
            approved_at=row["approved_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            verification_status=row["verification_status"],
            audit_reference=row["audit_reference"],
        )

    def insert_deployment_rollback(self, rb: DeploymentRollback) -> None:
        """Insert a DeploymentRollback entry."""
        sql = """
        INSERT INTO phase25_deployment_rollbacks (
            rollback_id, deployment_id, from_version, to_version, reason,
            approved_by, approved_at, rollback_status, verification_status, audit_reference
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        with self.conn:
            self.conn.execute(
                sql,
                (
                    rb.rollback_id,
                    rb.deployment_id,
                    rb.from_version,
                    rb.to_version,
                    rb.reason,
                    rb.approved_by,
                    rb.approved_at,
                    rb.rollback_status,
                    rb.verification_status,
                    rb.audit_reference,
                ),
            )

    def aggregate_metrics(self) -> dict[str, Any]:
        """Return aggregate metrics on deployment readiness reports and operations."""
        cursor = self.conn.execute("SELECT readiness_status, count(*) as cnt FROM phase25_readiness_reports GROUP BY readiness_status;")
        counts = {row["readiness_status"]: row["cnt"] for row in cursor.fetchall()}
        return {
            "total_reports": sum(counts.values()),
            "status_counts": counts,
        }
