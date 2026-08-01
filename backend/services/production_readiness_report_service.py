"""Phase 15 Steps 26-27: the final, immutable Text/NLP production
readiness report and the explicit final Admin production-acceptance
decision.

The report never re-implements any subsystem check -- it composes
`ProductionDeploymentReadinessService.assess()` (itself a read of
Steps 17-21's own results) plus the latest regression run, and is
append-only/versioned by the database triggers already defined on
`production_readiness_reports`. The acceptance review binds to the
*latest* report only and to a real fingerprint of whatever model/RAG
state is currently active, so a review can never be silently reused
against a report or production state that has since changed. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.production_deployment_readiness_service import (
    ProductionDeploymentReadinessService,
)
from core_model.production_readiness import ACCEPTANCE_DECISIONS

logger = logging.getLogger(__name__)

KNOWN_LIMITATIONS = (
    "Training and evaluation datasets remain small-scale relative to production LLM "
    "norms; readiness reflects the scale of data actually available in this project.",
    "The RAG track's automated tests use the deterministic_test_embedding provider; a "
    "real embedding-model swap should be re-validated before production RAG activation.",
    "Canary result sample sizes are small by construction (bounded fixture-prompt "
    "counts); canary metrics should be read as directional, not statistically final.",
    "API-abuse readiness is a static/configuration assessment, not a live load or "
    "penetration test.",
)


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
                event_type=f"production_readiness_report_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_readiness_report",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "production_readiness_report_audit_write_failed", extra={"action": action}
        )


def _derive_recommendation(deployment: dict[str, Any]) -> str:
    # Phase 15A Step 26: reads directly off `ProductionDeploymentReadiness
    # Service.assess()`'s own checks (which already require the canonical,
    # manifest-bound regression run specifically -- via the
    # `canonical_regression_finalized` event, not just "the most recent
    # regression run of any kind") rather than re-deriving readiness from
    # a separately-fetched latest-run status that could, in principle,
    # point at an unrelated, non-manifest-bound run.
    status = deployment["result_status"]
    if status == "blocked":
        return "blocked"
    if status != "ready":
        return "not_ready"
    if deployment["checks"].get("canonical_regression") == "passed":
        return "ready_for_text_nlp_production"
    # deployment_status == "ready" already guarantees canonical_regression
    # is at least "passed_with_environment_limitations" (assess() would
    # have blocked otherwise) -- a real, environment-only gap, not a
    # product failure, downgrades to a conditional recommendation instead
    # of the unconditional one.
    return "ready_with_conditions"


class ProductionReadinessReportService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._deployment = ProductionDeploymentReadinessService(settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def compile_report(self, *, admin_id: str) -> dict[str, Any]:
        deployment = self._deployment.assess(admin_id=admin_id)
        regression_runs = self.repository.list_regression_runs(limit=1)
        latest_regression = regression_runs[0] if regression_runs else None
        regression_results = (
            self.repository.list_regression_results(latest_regression["public_id"])
            if latest_regression else []
        )
        overview = self.repository.overview_counts()

        report_payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "deployment_readiness": deployment,
            "regression": {"run": latest_regression, "results": regression_results},
            "production_readiness_overview": overview,
            "known_limitations": list(KNOWN_LIMITATIONS),
        }
        checksum = hashlib.sha256(dumps_json(report_payload).encode("utf-8")).hexdigest()
        recommendation = _derive_recommendation(deployment)

        recorded = self.repository.add_readiness_report(
            {
                "report": report_payload,
                "report_checksum_sha256": checksum,
                "recommendation": recommendation,
                "finalized_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit, action="compile", actor_reference=admin_id,
            resource_public_id=recorded["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"recommendation": recommendation},
        )
        return recorded


class ProductionAcceptanceReviewService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _active_state_checksums(self) -> tuple[str | None, str | None]:
        with database_connection(self.settings.resolved_database_path) as connection:
            model_row = connection.execute(
                """SELECT v.eligibility_checksum_sha256
                FROM inference_model_assignments a
                JOIN inference_assignment_versions v ON v.public_id = a.current_version_public_id
                WHERE a.status='active' ORDER BY a.id DESC LIMIT 1"""
            ).fetchone()
            rag_row = connection.execute(
                """SELECT index_checksum_sha256 FROM production_rag_release_candidates
                WHERE production_visible=1 ORDER BY id DESC LIMIT 1"""
            ).fetchone()
        return (
            model_row[0] if model_row else None,
            rag_row[0] if rag_row else None,
        )

    def submit_review(
        self,
        readiness_report_public_id: str,
        decision: str,
        reason: str,
        *,
        admin_id: str,
        conditions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if decision not in ACCEPTANCE_DECISIONS:
            raise ValidationError(f"unknown acceptance decision: {decision!r}")
        if not reason.strip():
            raise ValidationError("a production acceptance decision requires a non-empty reason")

        latest = self.repository.get_latest_readiness_report()
        if latest is None or latest["public_id"] != readiness_report_public_id:
            raise ValidationError(
                "only the latest production readiness report may be reviewed -- a newer "
                "report exists (or none was found); compile and review the latest one"
            )

        active_model_checksum, active_rag_checksum = self._active_state_checksums()
        target_fingerprint = hashlib.sha256(
            dumps_json(
                {
                    "report_checksum": latest["report_checksum_sha256"],
                    "active_model_checksum": active_model_checksum,
                    "active_rag_checksum": active_rag_checksum,
                }
            ).encode("utf-8")
        ).hexdigest()

        recorded = self.repository.add_acceptance_review(
            readiness_report_public_id,
            {
                "decision": decision,
                "reason": reason,
                "conditions": conditions or {},
                "reviewer_admin_public_id": admin_id,
                "report_checksum": latest["report_checksum_sha256"],
                "active_model_checksum": active_model_checksum,
                "active_rag_checksum": active_rag_checksum,
                "target_fingerprint": target_fingerprint,
            },
        )
        _audit(
            self._audit, action="submit_review", actor_reference=admin_id,
            resource_public_id=recorded["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"decision": decision},
        )
        return recorded


__all__ = ["ProductionReadinessReportService", "ProductionAcceptanceReviewService"]
