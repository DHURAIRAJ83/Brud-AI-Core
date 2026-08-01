"""Phase 14 Step 25: human evaluation on a bounded multilingual prompt
set.

Append-only, attributed reviews across the 10 fixed
`core_model.training_incremental.HUMAN_REVIEW_DIMENSIONS`. A
checkpoint must be `evaluated` (automated evaluation already run)
before a human review can be recorded -- human review augments, never
replaces, the automated signal. See
docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from core_model.training_incremental import HUMAN_REVIEW_DECISIONS, HUMAN_REVIEW_DIMENSIONS

logger = logging.getLogger(__name__)

_EVALUATED_OR_LATER_STATUSES = ("evaluated", "accepted_candidate", "rejected")


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
                event_type=f"incremental_training_human_review_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="incremental_training_human_review",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "incremental_training_human_review_audit_write_failed", extra={"action": action}
        )


class IncrementalTrainingHumanReviewService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def add_review(
        self, checkpoint_public_id: str, values: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        checkpoint = self._training.get_checkpoint(checkpoint_public_id)
        if checkpoint["status"] not in _EVALUATED_OR_LATER_STATUSES:
            raise ValidationError(
                "a checkpoint must be automatically evaluated before a human review can be "
                "recorded"
            )
        decision = values["decision"]
        if decision not in HUMAN_REVIEW_DECISIONS:
            raise ValidationError(f"unknown human review decision: {decision!r}")
        if not values.get("prompt_text", "").strip():
            raise ValidationError("a prompt_text is required for a human review")

        dimensions = {
            dimension: values.get(dimension) for dimension in HUMAN_REVIEW_DIMENSIONS
            if dimension in values
        }
        review = self._training.add_human_review(
            checkpoint_public_id,
            {
                **dimensions,
                "prompt_text": values["prompt_text"],
                "decision": decision,
                "notes": values.get("notes", ""),
                "reviewer_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="add_review", actor_reference=admin_id,
            resource_public_id=review["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"checkpoint_public_id": checkpoint_public_id, "decision": decision},
        )
        return review

    def list_reviews(self, checkpoint_public_id: str) -> list[dict[str, Any]]:
        return self._training.list_human_reviews(checkpoint_public_id)


__all__ = ["IncrementalTrainingHumanReviewService"]
