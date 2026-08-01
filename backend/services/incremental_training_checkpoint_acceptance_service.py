"""Phase 14 Step 27-28: explicit Admin checkpoint acceptance and
Model Registry handoff.

Checkpoint acceptance is a separate, explicit, stale-protected Admin
decision -- distinct from the report's advisory recommendation.
`major_regression` (from `IncrementalTrainingComparisonService`) is a
hard, non-overridable block on any *accepting* decision, per Step 26.

When (and only when) a checkpoint is accepted, this service hands it
to the registry via the *existing, unmodified*
`PretrainingService.promote()` -- the same mechanism Phase 9's own
checkpoint promotion uses -- which can only ever write
`core_model_versions.lifecycle_status='staging'`. Nothing in this
phase writes `'active'` or calls `ModelReleaseService`; that boundary
is structural, not a convention (see
docs/training/phase14_incremental_language_training_plan.md, "Two
production-adjacent lines this phase must never cross").
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.pretraining_service import PretrainingService
from core_model.training_incremental import (
    BLOCKING_REGRESSION_RESULTS,
    CHECKPOINT_ACCEPTANCE_DECISIONS,
    MODEL_CANDIDATE_LIFECYCLE_STATUS,
)

logger = logging.getLogger(__name__)

_ACCEPTING_DECISIONS = ("accepted_candidate", "accepted_with_conditions")


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
                event_type=f"incremental_training_checkpoint_acceptance_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="incremental_training_checkpoint_acceptance",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "incremental_training_checkpoint_acceptance_audit_write_failed",
            extra={"action": action},
        )


class IncrementalTrainingCheckpointAcceptanceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)
        self._pretraining = PretrainingService(
            PretrainingRepository(settings.resolved_database_path), settings
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def accept(
        self, checkpoint_public_id: str, report_public_id: str, values: dict[str, Any],
        *, admin_id: str,
    ) -> dict[str, Any]:
        decision = values["decision"]
        if decision not in CHECKPOINT_ACCEPTANCE_DECISIONS:
            raise ValidationError(f"unknown checkpoint acceptance decision: {decision!r}")
        if not values.get("reason", "").strip():
            raise ValidationError("a reason is required to accept or reject a checkpoint")

        checkpoint = self._training.get_checkpoint(checkpoint_public_id)
        if checkpoint["status"] not in ("evaluated",):
            raise ValidationError(
                f"checkpoint status '{checkpoint['status']}' is not eligible for an acceptance "
                "decision -- it must be 'evaluated' (and not already accepted/rejected)"
            )
        report = self._training.get_report(report_public_id)
        if report["run_public_id"] != checkpoint["run_public_id"]:
            raise ValidationError("report does not belong to this checkpoint's run")
        latest_report = self._training.get_latest_report(checkpoint["run_public_id"])
        if latest_report is None or latest_report["public_id"] != report_public_id:
            raise ValidationError(
                "a newer report exists for this run -- accept against the latest report"
            )

        if decision in _ACCEPTING_DECISIONS:
            comparisons = self._training.list_comparisons(checkpoint_public_id)
            blocking = [c for c in comparisons if c["result_status"] in BLOCKING_REGRESSION_RESULTS]
            if blocking:
                raise ValidationError(
                    "this checkpoint has a major_regression comparison result -- acceptance is "
                    "blocked and cannot be overridden"
                )

        target_fingerprint = hashlib.sha256(
            f"{checkpoint['checkpoint_checksum']}:{report['report_checksum_sha256']}".encode()
        ).hexdigest()

        model_candidate_public_id = None
        if decision in _ACCEPTING_DECISIONS:
            override_comment = values.get("override_comment") or values["reason"]
            promotion = self._pretraining.promote(
                checkpoint["underlying_checkpoint_public_id"], admin_id, override_comment
            )
            model_candidate_public_id = promotion["promoted_model_version_public_id"]

        acceptance = self._training.add_acceptance(
            checkpoint_public_id,
            {
                "report_public_id": report_public_id,
                "decision": decision,
                "reason": values["reason"],
                "conditions": values.get("conditions", {}),
                "reviewer_admin_public_id": admin_id,
                "report_checksum_sha256": report["report_checksum_sha256"],
                "checkpoint_checksum": checkpoint["checkpoint_checksum"],
                "target_fingerprint": target_fingerprint,
                "model_candidate_public_id": model_candidate_public_id,
            },
        )

        new_checkpoint_status = {
            "accepted_candidate": "accepted_candidate",
            "accepted_with_conditions": "accepted_candidate",
            "rejected": "rejected",
            "needs_more_testing": "evaluated",
        }[decision]
        self._training.update_checkpoint_status(checkpoint_public_id, new_checkpoint_status)

        _audit(
            self._audit, action="accept", actor_reference=admin_id,
            resource_public_id=acceptance["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={
                "decision": decision,
                "model_candidate_public_id": model_candidate_public_id,
                "model_candidate_lifecycle_status": (
                    MODEL_CANDIDATE_LIFECYCLE_STATUS if model_candidate_public_id else None
                ),
            },
        )
        return acceptance

    def get_latest_acceptance(self, checkpoint_public_id: str) -> dict[str, Any] | None:
        return self._training.get_latest_acceptance(checkpoint_public_id)

    def list_acceptances(self, checkpoint_public_id: str) -> list[dict[str, Any]]:
        return self._training.list_acceptances(checkpoint_public_id)


__all__ = ["IncrementalTrainingCheckpointAcceptanceService"]
