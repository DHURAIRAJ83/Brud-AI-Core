"""Phase 26 Additive SQLite Database Repository for Production Observability, Incident Management & Recovery Governance."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any, Sequence

from core_model.capabilities.production_observability_service import (
    HealthCheckItem,
    HealthTrendComparison,
    IncidentRecord,
    IncidentReview,
    ObservabilityProvenance,
    RecoveryOperation,
    RecoveryRecommendation,
    RuntimeHealthReport,
)


class ObservabilityRepository:
    """SQLite Repository for Phase 26 Production Observability tables."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._create_tables()

    def _create_tables(self) -> None:
        """Create additive Phase 26 tables and indexes."""
        cursor = self.conn.cursor()

        # Health Reports
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS phase26_health_reports (
                health_report_id TEXT PRIMARY KEY,
                deployment_id TEXT NOT NULL,
                release_id TEXT NOT NULL,
                active_version TEXT NOT NULL,
                overall_status TEXT NOT NULL,
                health_score REAL NOT NULL,
                created_at TEXT NOT NULL,
                provenance_json TEXT NOT NULL
            )
            """
        )

        # Health Checks
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS phase26_health_checks (
                check_id TEXT NOT NULL,
                health_report_id TEXT NOT NULL,
                category TEXT NOT NULL,
                component TEXT NOT NULL,
                status TEXT NOT NULL,
                severity TEXT NOT NULL,
                observed_value TEXT NOT NULL,
                expected_value TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                evidence TEXT NOT NULL,
                PRIMARY KEY (check_id, health_report_id),
                FOREIGN KEY (health_report_id) REFERENCES phase26_health_reports(health_report_id)
            )
            """
        )

        # Health Comparisons
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS phase26_health_comparisons (
                comparison_id TEXT PRIMARY KEY,
                report_id_a TEXT NOT NULL,
                report_id_b TEXT NOT NULL,
                trend_status TEXT NOT NULL,
                score_delta REAL NOT NULL,
                changed_checks_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # Incidents
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS phase26_incidents (
                incident_id TEXT PRIMARY KEY,
                health_report_id TEXT NOT NULL,
                deployment_id TEXT NOT NULL,
                release_id TEXT NOT NULL,
                component TEXT NOT NULL,
                severity TEXT NOT NULL,
                category TEXT NOT NULL,
                detected_condition TEXT NOT NULL,
                evidence TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                provenance_json TEXT NOT NULL
            )
            """
        )

        # Incident Reviews
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS phase26_incident_reviews (
                review_id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                reviewed_by TEXT NOT NULL,
                reviewed_at TEXT NOT NULL,
                action TEXT NOT NULL,
                notes TEXT,
                review_hash TEXT NOT NULL,
                FOREIGN KEY (incident_id) REFERENCES phase26_incidents(incident_id)
            )
            """
        )

        # Recovery Recommendations
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS phase26_recovery_recommendations (
                recommendation_id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                reason TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                provenance_json TEXT NOT NULL,
                FOREIGN KEY (incident_id) REFERENCES phase26_incidents(incident_id)
            )
            """
        )

        # Recovery Operations
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS phase26_recovery_operations (
                recovery_id TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                approved_at TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT NOT NULL,
                execution_status TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                audit_reference TEXT NOT NULL,
                idempotency_key TEXT UNIQUE NOT NULL,
                FOREIGN KEY (incident_id) REFERENCES phase26_incidents(incident_id)
            )
            """
        )

        # Health Locks
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS phase26_health_locks (
                lock_key TEXT PRIMARY KEY,
                incident_id TEXT NOT NULL,
                acquired_by TEXT NOT NULL,
                acquired_at TEXT NOT NULL
            )
            """
        )

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_p26_reports_deployment ON phase26_health_reports(deployment_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_p26_reports_release ON phase26_health_reports(release_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_p26_checks_report ON phase26_health_checks(health_report_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_p26_incidents_deployment ON phase26_incidents(deployment_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_p26_incidents_status ON phase26_incidents(status)")

        self.conn.commit()

    def insert_health_report(self, report: RuntimeHealthReport) -> None:
        """Insert a runtime health observation report and checks."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO phase26_health_reports (
                health_report_id, deployment_id, release_id, active_version,
                overall_status, health_score, created_at, provenance_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.health_report_id,
                report.deployment_id,
                report.release_id,
                report.active_version,
                report.overall_status,
                report.health_score,
                report.created_at,
                json.dumps(report.provenance.to_dict()),
            ),
        )

        for check in report.checks:
            cursor.execute(
                """
                INSERT INTO phase26_health_checks (
                    check_id, health_report_id, category, component, status,
                    severity, observed_value, expected_value, timestamp, evidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    check.check_id,
                    report.health_report_id,
                    check.category,
                    check.component,
                    check.status,
                    check.severity,
                    check.observed_value,
                    check.expected_value,
                    check.timestamp,
                    check.evidence,
                ),
            )

        self.conn.commit()

    def get_health_report(self, health_report_id: str) -> RuntimeHealthReport | None:
        """Fetch a health report by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT health_report_id, deployment_id, release_id, active_version,
                   overall_status, health_score, created_at, provenance_json
            FROM phase26_health_reports
            WHERE health_report_id = ?
            """,
            (health_report_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        # Fetch checks
        cursor.execute(
            """
            SELECT check_id, category, component, status, severity,
                   observed_value, expected_value, timestamp, evidence
            FROM phase26_health_checks
            WHERE health_report_id = ?
            """,
            (health_report_id,),
        )
        check_rows = cursor.fetchall()
        checks = tuple(
            HealthCheckItem(
                check_id=cr[0],
                category=cr[1],
                component=cr[2],
                status=cr[3],
                severity=cr[4],
                observed_value=cr[5],
                expected_value=cr[6],
                timestamp=cr[7],
                evidence=cr[8],
            )
            for cr in check_rows
        )

        prov_dict = json.loads(row[7])
        prov = ObservabilityProvenance(**prov_dict)

        return RuntimeHealthReport(
            health_report_id=row[0],
            deployment_id=row[1],
            release_id=row[2],
            active_version=row[3],
            overall_status=row[4],
            health_score=row[5],
            checks=checks,
            created_at=row[6],
            provenance=prov,
        )

    def insert_incident(self, incident: IncidentRecord) -> None:
        """Insert a structured incident record."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO phase26_incidents (
                incident_id, health_report_id, deployment_id, release_id, component,
                severity, category, detected_condition, evidence, status, created_at, provenance_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident.incident_id,
                incident.health_report_id,
                incident.deployment_id,
                incident.release_id,
                incident.component,
                incident.severity,
                incident.category,
                incident.detected_condition,
                incident.evidence,
                incident.status,
                incident.created_at,
                json.dumps(incident.provenance.to_dict()),
            ),
        )
        self.conn.commit()

    def get_incident(self, incident_id: str) -> IncidentRecord | None:
        """Fetch an incident record by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT incident_id, health_report_id, deployment_id, release_id, component,
                   severity, category, detected_condition, evidence, status, created_at, provenance_json
            FROM phase26_incidents
            WHERE incident_id = ?
            """,
            (incident_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        prov_dict = json.loads(row[11])
        prov = ObservabilityProvenance(**prov_dict)

        return IncidentRecord(
            incident_id=row[0],
            health_report_id=row[1],
            deployment_id=row[2],
            release_id=row[3],
            component=row[4],
            severity=row[5],
            category=row[6],
            detected_condition=row[7],
            evidence=row[8],
            status=row[9],
            created_at=row[10],
            provenance=prov,
        )

    def update_incident_status(self, incident_id: str, new_status: str) -> None:
        """Update incident status."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE phase26_incidents SET status = ? WHERE incident_id = ?",
            (new_status, incident_id),
        )
        self.conn.commit()

    def insert_incident_review(self, review: IncidentReview) -> None:
        """Insert an incident review record."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO phase26_incident_reviews (
                review_id, incident_id, reviewed_by, reviewed_at, action, notes, review_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review.review_id,
                review.incident_id,
                review.reviewed_by,
                review.reviewed_at,
                review.action,
                review.notes,
                review.review_hash,
            ),
        )
        self.conn.commit()

    def insert_recovery_recommendation(self, rec: RecoveryRecommendation) -> None:
        """Insert a recovery recommendation record."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO phase26_recovery_recommendations (
                recommendation_id, incident_id, recommended_action, reason, risk_level, provenance_json
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                rec.recommendation_id,
                rec.incident_id,
                rec.recommended_action,
                rec.reason,
                rec.risk_level,
                json.dumps(rec.provenance.to_dict()),
            ),
        )
        self.conn.commit()

    def insert_recovery_operation(self, op: RecoveryOperation) -> None:
        """Insert a recovery operation execution record."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO phase26_recovery_operations (
                recovery_id, incident_id, approved_by, approved_at, action,
                reason, execution_status, verification_status, audit_reference, idempotency_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                op.recovery_id,
                op.incident_id,
                op.approved_by,
                op.approved_at,
                op.action,
                op.reason,
                op.execution_status,
                op.verification_status,
                op.audit_reference,
                op.idempotency_key,
            ),
        )
        self.conn.commit()

    def get_recovery_operation_by_idempotency_key(self, idempotency_key: str) -> RecoveryOperation | None:
        """Lookup recovery operation by idempotency key."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT recovery_id, incident_id, approved_by, approved_at, action,
                   reason, execution_status, verification_status, audit_reference, idempotency_key
            FROM phase26_recovery_operations
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return RecoveryOperation(
            recovery_id=row[0],
            incident_id=row[1],
            approved_by=row[2],
            approved_at=row[3],
            action=row[4],
            reason=row[5],
            execution_status=row[6],
            verification_status=row[7],
            audit_reference=row[8],
            idempotency_key=row[9],
        )

    def acquire_health_lock(self, lock_key: str, incident_id: str, acquired_by: str) -> bool:
        """Attempt to acquire a concurrency lock for recovery operation."""
        cursor = self.conn.cursor()
        now_str = datetime.now(UTC).isoformat()
        try:
            cursor.execute(
                """
                INSERT INTO phase26_health_locks (lock_key, incident_id, acquired_by, acquired_at)
                VALUES (?, ?, ?, ?)
                """,
                (lock_key, incident_id, acquired_by, now_str),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def release_health_lock(self, lock_key: str) -> None:
        """Release a concurrency lock."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM phase26_health_locks WHERE lock_key = ?", (lock_key,))
        self.conn.commit()
