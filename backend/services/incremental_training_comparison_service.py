"""Phase 14 Steps 22-24: deterministic checkpoint comparison,
regression detection, and catastrophic-forgetting checks.

Reuses the *existing, unmodified* `TrainingEvaluationService.
compare_checkpoints()` / `compare_runs()` for the raw side-by-side
deltas (loss, tokens, seeds, compatibility) -- this service adds only
the governance layer those general-purpose comparisons don't have: a
deterministic classification of the loss delta into
`core_model.training_incremental.REGRESSION_RESULTS`
(`improved`/`unchanged`/`minor_regression`/`major_regression`/
`not_comparable`). A `major_regression` classification here does not
itself block anything -- Task #189's checkpoint-acceptance service is
what enforces "major_regression must block acceptance"; this service
only measures and records.

Comparing a checkpoint against its own parent (rather than an
arbitrary baseline) is what makes a comparison a *forgetting check*
(Step 23) rather than a general comparison -- both use identical
mechanics, only `comparison_type` and which baseline is passed differ.
See docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.database.repositories.training_reliability import TrainingReliabilityRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.training_evaluation_service import TrainingEvaluationService
from core_model.training_incremental import COMPARISON_TYPES

logger = logging.getLogger(__name__)

IMPROVEMENT_THRESHOLD = -0.02
MINOR_REGRESSION_THRESHOLD = 0.05
MAJOR_REGRESSION_THRESHOLD = 0.20


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
                event_type=f"incremental_training_comparison_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="incremental_training_comparison",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "incremental_training_comparison_audit_write_failed", extra={"action": action}
        )


def classify_regression(run_delta: dict[str, Any]) -> str:
    """Deterministic loss-delta classification. `left` is always the
    candidate checkpoint's run, `right` the baseline's."""

    fields = run_delta.get("fields", {})
    left_loss = fields.get("final_validation_loss", {}).get("left")
    right_loss = fields.get("final_validation_loss", {}).get("right")
    if left_loss is None or right_loss is None or right_loss == 0:
        return "not_comparable"
    delta_ratio = (left_loss - right_loss) / right_loss
    if delta_ratio <= IMPROVEMENT_THRESHOLD:
        return "improved"
    if delta_ratio <= MINOR_REGRESSION_THRESHOLD:
        return "unchanged"
    if delta_ratio <= MAJOR_REGRESSION_THRESHOLD:
        return "minor_regression"
    return "major_regression"


class IncrementalTrainingComparisonService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)
        self._pretraining_repository = PretrainingRepository(settings.resolved_database_path)
        self._evaluation = TrainingEvaluationService(
            self._pretraining_repository,
            TrainingReliabilityRepository(settings.resolved_database_path),
            settings,
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _underlying_job_public_id(self, underlying_checkpoint_public_id: str) -> str:
        with self._pretraining_repository.transaction() as connection:
            row = connection.execute(
                """SELECT j.public_id FROM pretraining_checkpoints c
                JOIN pretraining_jobs j ON j.id = c.pretraining_job_id
                WHERE c.public_id=?""",
                (underlying_checkpoint_public_id,),
            ).fetchone()
        if not row:
            raise ValidationError("the underlying checkpoint's training job could not be resolved")
        return row["public_id"]

    def compare(
        self,
        checkpoint_public_id: str,
        baseline_checkpoint_public_id: str,
        *,
        comparison_type: str = "general_comparison",
        admin_id: str,
    ) -> dict[str, Any]:
        if comparison_type not in COMPARISON_TYPES:
            raise ValidationError(f"unknown comparison_type: {comparison_type!r}")
        checkpoint = self._training.get_checkpoint(checkpoint_public_id)
        if checkpoint["status"] not in ("evaluated", "accepted_candidate"):
            raise ValidationError(
                "only an evaluated checkpoint may be compared -- evaluate it first"
            )
        baseline = self._training.get_checkpoint(baseline_checkpoint_public_id)

        checkpoint_delta = self._evaluation.compare_checkpoints(
            left=checkpoint["underlying_checkpoint_public_id"],
            right=baseline["underlying_checkpoint_public_id"],
            admin_id=admin_id,
        )
        run_delta = self._evaluation.compare_runs(
            left=self._underlying_job_public_id(checkpoint["underlying_checkpoint_public_id"]),
            right=self._underlying_job_public_id(baseline["underlying_checkpoint_public_id"]),
            admin_id=admin_id,
        )
        result_status = classify_regression(run_delta)

        comparison = self._training.add_comparison(
            checkpoint_public_id,
            {
                "parent_checkpoint_public_id": baseline_checkpoint_public_id,
                "comparison_type": comparison_type,
                "dimension": "overall",
                "result_status": result_status,
                "metrics": {
                    "checkpoint_delta": checkpoint_delta,
                    "run_delta": run_delta,
                    "compatibility": checkpoint_delta["compatibility"],
                },
                "source_evaluation_ids": [
                    checkpoint_delta.get("public_id"), run_delta.get("public_id"),
                ],
            },
        )
        _audit(
            self._audit, action="compare", actor_reference=admin_id,
            resource_public_id=comparison["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"comparison_type": comparison_type, "result_status": result_status},
        )
        return comparison

    def compare_to_parent(
        self, checkpoint_public_id: str, parent_checkpoint_public_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        """A catastrophic-forgetting check: compares the candidate
        checkpoint's own parent, not an arbitrary baseline."""

        return self.compare(
            checkpoint_public_id, parent_checkpoint_public_id,
            comparison_type="forgetting_check", admin_id=admin_id,
        )


__all__ = ["IncrementalTrainingComparisonService", "classify_regression"]
