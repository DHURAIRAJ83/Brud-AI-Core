"""Phase 14 Steps 19-21: checkpoint integrity verification and
automated evaluation.

Both executable training strategies (`continued_pretraining` and
`incremental_sft`, the latter via its own internal
`job_mode='bounded_pretraining'` wrapping) ultimately produce a
`pretraining_checkpoints` row -- so this service delegates file/
checksum/manifest verification to the *existing, unmodified*
`PretrainingService.verify_checkpoint()` and evaluation to
`PretrainingService.evaluate()` + `TrainingEvaluationService.
assess_quality()` (which already covers train/validation loss gap,
checksum-reference validation, resume consistency, and non-finite
detection -- the Step 23 memorization/overfitting signals). A
Phase 14 checkpoint is never marked `evaluated` differently based on
the *outcome* -- an automated evaluation only records a signal; it
never itself accepts or rejects a checkpoint (that is Task #189's
separate, explicit Admin decision). See
docs/training/phase14_incremental_language_training_plan.md.
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
from backend.services.pretraining_service import PretrainingService
from backend.services.training_evaluation_service import TrainingEvaluationService

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
                event_type=f"incremental_training_checkpoint_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="incremental_training_checkpoint",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "incremental_training_checkpoint_audit_write_failed", extra={"action": action}
        )


class IncrementalTrainingCheckpointService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)
        self._pretraining_repository = PretrainingRepository(settings.resolved_database_path)
        self._pretraining = PretrainingService(self._pretraining_repository, settings)
        self._quality = TrainingEvaluationService(
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

    def verify(self, checkpoint_public_id: str, *, admin_id: str) -> dict[str, Any]:
        checkpoint = self._training.get_checkpoint(checkpoint_public_id)
        if checkpoint["status"] not in ("created", "verified"):
            raise ValidationError(
                f"checkpoint status '{checkpoint['status']}' cannot be (re-)verified"
            )
        result = self._pretraining.verify_checkpoint(
            checkpoint["underlying_checkpoint_public_id"], admin_id
        )
        new_status = "verified" if result["verified"] else "corrupt"
        updated = self._training.update_checkpoint_status(checkpoint_public_id, new_status)
        _audit(
            self._audit, action="verify", actor_reference=admin_id,
            resource_public_id=checkpoint_public_id, outcome=AuditOutcome.SUCCESS,
            metadata={"status": new_status},
        )
        return updated

    def evaluate(self, checkpoint_public_id: str, *, admin_id: str) -> dict[str, Any]:
        checkpoint = self._training.get_checkpoint(checkpoint_public_id)
        if checkpoint["status"] != "verified":
            raise ValidationError(
                "only a verified checkpoint may be evaluated -- verify it first"
            )
        self._training.update_checkpoint_status(checkpoint_public_id, "evaluation_pending")
        job_public_id = self._underlying_job_public_id(
            checkpoint["underlying_checkpoint_public_id"]
        )

        loss_evaluation = self._pretraining.evaluate(job_public_id, admin_id)
        quality = self._quality.assess_quality(job_public_id, admin_id)

        evaluations = [
            self._training.add_evaluation(
                checkpoint_public_id,
                {
                    "evaluation_type": "validation_loss",
                    "result_status": "completed",
                    "automated": True,
                    "score": loss_evaluation.get("summary", {}).get("validation_loss"),
                    "details": {"pretraining_evaluation_public_id": loss_evaluation["public_id"]},
                },
            ),
            self._training.add_evaluation(
                checkpoint_public_id,
                {
                    "evaluation_type": "quality_readiness",
                    "result_status": quality["readiness_status"],
                    "automated": True,
                    "score": quality.get("overall_score"),
                    "details": {
                        "dimension_scores": quality.get("dimension_scores"),
                        "issues": quality.get("issues"),
                    },
                },
            ),
        ]
        # An automated evaluation only records a signal -- it never accepts
        # or rejects on its own, regardless of readiness_status (Step 20:
        # "must not accept solely because training loss decreased" applies
        # symmetrically to automated rejection too).
        updated = self._training.update_checkpoint_status(checkpoint_public_id, "evaluated")
        _audit(
            self._audit, action="evaluate", actor_reference=admin_id,
            resource_public_id=checkpoint_public_id, outcome=AuditOutcome.SUCCESS,
            metadata={"quality_readiness_status": quality["readiness_status"]},
        )
        return {"checkpoint": updated, "evaluations": evaluations, "quality": quality}


__all__ = ["IncrementalTrainingCheckpointService"]
