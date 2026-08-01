"""Phase 14 Step 26: immutable training report with an advisory
`checkpoint_recommendation`.

Deterministically aggregates a run's automated evaluations,
regression/forgetting comparisons, and bounded human reviews into one
versioned, checksum-stamped, append-only report. The
`checkpoint_recommendation` is advisory guidance for the Admin -- it
never accepts, rejects, activates, or releases anything on its own;
`IncrementalTrainingCheckpointAcceptanceService` is the only place a
binding decision is made. See
docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.models.domain import AuditEventCreate, AuditOutcome

logger = logging.getLogger(__name__)


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
                event_type=f"incremental_training_report_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="incremental_training_report",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("incremental_training_report_audit_write_failed", extra={"action": action})


def _recommend(
    evaluations: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    human_reviews: list[dict[str, Any]],
) -> str:
    """Deterministic, documented rubric -- advisory only. Never itself
    a training-eligibility or production-readiness decision."""

    if any(c["result_status"] == "major_regression" for c in comparisons):
        return "reject"
    if any(h["decision"] == "fail" for h in human_reviews):
        return "reject"
    if any(e["result_status"] == "blocked" for e in evaluations):
        return "reject"
    if not evaluations or not comparisons or not human_reviews:
        return "needs_more_evaluation"
    if any(h["decision"] == "needs_more_testing" for h in human_reviews):
        return "needs_more_evaluation"
    if any(c["result_status"] == "minor_regression" for c in comparisons):
        return "accept_with_conditions"
    if any(h["decision"] == "pass_with_conditions" for h in human_reviews):
        return "accept_with_conditions"
    if any(e["result_status"] == "warning" for e in evaluations):
        return "accept_with_conditions"
    return "accept_candidate"


class IncrementalTrainingReportService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def finalize_report(
        self, run_public_id: str, checkpoint_public_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        run = self._training.get_run(run_public_id)
        checkpoint = self._training.get_checkpoint(checkpoint_public_id)
        if checkpoint["run_public_id"] != run_public_id:
            raise ValidationError("checkpoint does not belong to this run")
        if checkpoint["status"] not in ("evaluated", "accepted_candidate", "rejected"):
            raise ValidationError(
                "a checkpoint must be automatically evaluated before a report can be finalized"
            )

        evaluations = self._training.list_evaluations(checkpoint_public_id)
        comparisons = self._training.list_comparisons(checkpoint_public_id)
        human_reviews = self._training.list_human_reviews(checkpoint_public_id)
        recommendation = _recommend(evaluations, comparisons, human_reviews)

        report_body = {
            "run_public_id": run_public_id,
            "checkpoint_public_id": checkpoint_public_id,
            "underlying_checkpoint_public_id": checkpoint["underlying_checkpoint_public_id"],
            "run_status": run["status"],
            "evaluations": evaluations,
            "comparisons": comparisons,
            "human_reviews": human_reviews,
            "checkpoint_recommendation": recommendation,
        }
        report_checksum = hashlib.sha256(dumps_json(report_body).encode()).hexdigest()

        report = self._training.add_report(
            run_public_id,
            {
                "report": report_body,
                "report_checksum_sha256": report_checksum,
                "checkpoint_recommendation": recommendation,
                # Phase 14 never assesses production-release readiness --
                # that remains ModelReleaseService's separate, later, and
                # out-of-scope mechanism.
                "production_release_readiness": "not_assessed",
                "recommended_next_action": (
                    "await explicit Admin checkpoint acceptance -- this report is advisory only"
                ),
                "finalized_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="finalize", actor_reference=admin_id,
            resource_public_id=report["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"checkpoint_recommendation": recommendation},
        )
        return report

    def get_latest_report(self, run_public_id: str) -> dict[str, Any] | None:
        return self._training.get_latest_report(run_public_id)

    def list_reports(self, run_public_id: str) -> list[dict[str, Any]]:
        return self._training.list_reports(run_public_id)


__all__ = ["IncrementalTrainingReportService"]
