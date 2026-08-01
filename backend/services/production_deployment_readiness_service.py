"""Phase 15 Steps 22-23: deployment readiness and system health.

`ProductionDeploymentReadinessService` never re-runs Steps 17-21 --
it only reads back whatever the admin has *already* run through the
dedicated artifact-security/API-abuse/secret-scan/backup/restore
services and refuses to call the deployment "ready" on missing
evidence rather than treating absence as a pass ("Deployment success
!= Security verification complete" per the Phase 15 invariants).
`ProductionSystemHealthService` reuses the same database PRAGMA checks
`/admin/system/database` already exposes. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import migration_status
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome

logger = logging.getLogger(__name__)

_READINESS_EVENT_SCAN_LIMIT = 100


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"production_deployment_readiness_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_deployment_readiness_check",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "production_deployment_readiness_audit_write_failed", extra={"action": action}
        )


def _latest_event_result_status(events: list[dict[str, Any]], event_type: str) -> str | None:
    for event in events:
        if event["event_type"] == event_type:
            summary = event.get("summary", "")
            if summary.startswith("result_status="):
                return summary.split("=", 1)[1].split(" ", 1)[0]
    return None


class ProductionDeploymentReadinessService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def assess(self, *, admin_id: str) -> dict[str, Any]:
        checks: dict[str, Any] = {}
        blocking: list[str] = []

        backup = self.repository.get_latest_backup_readiness_check("backup")
        checks["backup_readiness"] = backup["result_status"] if backup else "not_assessed"
        if backup is None:
            blocking.append("backup_readiness_never_assessed")
        elif backup["result_status"] == "failed":
            blocking.append("backup_readiness_failed")

        restore = self.repository.get_latest_backup_readiness_check("restore")
        checks["restore_readiness"] = restore["result_status"] if restore else "not_assessed"
        if restore is None:
            blocking.append("restore_readiness_never_assessed")
        elif restore["result_status"] == "failed":
            blocking.append("restore_readiness_failed")

        artifact_checks = self.repository.list_artifact_security_checks(limit=50)
        checks["artifact_security"] = (
            "not_assessed" if not artifact_checks
            else "failed" if any(c["result_status"] == "failed" for c in artifact_checks)
            else "passed"
        )
        if not artifact_checks:
            blocking.append("artifact_security_never_assessed")
        elif checks["artifact_security"] == "failed":
            blocking.append("artifact_security_failed")

        events = self.repository.list_readiness_events(limit=_READINESS_EVENT_SCAN_LIMIT)
        api_abuse_status = _latest_event_result_status(events, "api_abuse_readiness_assessed")
        checks["api_abuse_readiness"] = api_abuse_status or "not_assessed"
        if api_abuse_status is None:
            blocking.append("api_abuse_readiness_never_assessed")
        elif api_abuse_status == "failed":
            blocking.append("api_abuse_readiness_failed")

        secret_scan_status = _latest_event_result_status(
            events, "secret_redaction_mechanism_verified"
        )
        checks["secret_scan"] = secret_scan_status or "not_assessed"
        if secret_scan_status is None:
            blocking.append("secret_scan_never_assessed")
        elif secret_scan_status == "failed":
            blocking.append("secret_scan_failed")

        with database_connection(self.settings.resolved_database_path) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        checks["database_integrity"] = "passed" if integrity == "ok" else "failed"
        if integrity != "ok":
            blocking.append("database_integrity_check_failed")

        # Phase 15A Step 22: three additional never-assessed-blocks-readiness
        # checks, following the exact pattern above -- absence of evidence
        # is never treated as a pass.
        regression_status = _latest_event_result_status(events, "canonical_regression_finalized")
        checks["canonical_regression"] = regression_status or "not_assessed"
        if regression_status is None:
            blocking.append("canonical_regression_never_assessed")
        elif regression_status not in {"passed", "passed_with_environment_limitations"}:
            blocking.append("canonical_regression_failed")

        browser_result = self.repository.get_latest_regression_result_by_batch_prefix(
            "browser_e2e:"
        )
        browser_status = browser_result["status"] if browser_result else None
        checks["browser_verification"] = browser_status or "not_assessed"
        if browser_status is None:
            blocking.append("browser_verification_never_assessed")
        elif browser_status != "passed":
            blocking.append("browser_verification_failed")

        encryption_status = _latest_event_result_status(events, "backup_encryption_assessed")
        checks["backup_encryption"] = encryption_status or "not_assessed"
        if encryption_status is None:
            blocking.append("backup_encryption_never_assessed")
        elif encryption_status not in {"encrypted", "encrypted_with_conditions"}:
            blocking.append("backup_encryption_not_encrypted")

        never_assessed = [b for b in blocking if b.endswith("_never_assessed")]
        hard_failures = [b for b in blocking if not b.endswith("_never_assessed")]
        if hard_failures:
            result_status = "blocked"
        elif never_assessed:
            result_status = "not_ready"
        else:
            result_status = "ready"

        recorded = self.repository.add_deployment_readiness_check(
            {
                "result_status": result_status,
                "checks": checks,
                "blocking_reasons": blocking,
                "created_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="assess", actor_reference=admin_id,
            resource_public_id=recorded["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"result_status": result_status},
        )
        return recorded


class ProductionSystemHealthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def snapshot(self, *, admin_id: str) -> dict[str, Any]:
        with database_connection(self.settings.resolved_database_path) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
            instance_status_counts = dict(
                connection.execute(
                    "SELECT status, COUNT(*) FROM inference_runtime_instances GROUP BY status"
                ).fetchall()
            )
            assignment_status_counts = dict(
                connection.execute(
                    "SELECT status, COUNT(*) FROM inference_model_assignments GROUP BY status"
                ).fetchall()
            )

        schema_version = migration_status(self.settings.resolved_database_path)["current_version"]
        overview = self.repository.overview_counts()
        database_healthy = integrity == "ok"
        overview_failure_signals = (
            overview.get("activation_failures", 0)
            + overview.get("rollback_readiness_failures", 0)
            + overview.get("artifact_security_failures", 0)
        )
        overall_status = (
            "healthy" if database_healthy and overview_failure_signals == 0 else "degraded"
        )

        snapshot = {
            "overall_status": overall_status,
            "database": {
                "integrity": integrity, "journal_mode": journal_mode,
                "schema_version": schema_version,
            },
            "inference_instance_status_counts": instance_status_counts,
            "inference_assignment_status_counts": assignment_status_counts,
            "production_readiness_overview": overview,
        }
        event = self.repository.record_readiness_event(
            {
                "event_type": "system_health_snapshot",
                "resource_type": "system",
                "resource_public_id": "production_readiness",
                "summary": f"overall_status={overall_status}",
                "metadata": snapshot,
                "performed_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="snapshot", actor_reference=admin_id,
            resource_public_id=event["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"overall_status": overall_status},
        )
        return {**snapshot, "event": event}


__all__ = ["ProductionDeploymentReadinessService", "ProductionSystemHealthService"]
