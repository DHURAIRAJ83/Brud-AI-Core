"""Phase 14 Step 5 governed training-example transformation.

Every transformation preserves source lineage (the original accepted
Phase 12/13 record is never modified, only referenced), stores the
transformed candidate separately, records the transformation method
and template version, and requires human review before a candidate is
eligible for dataset promotion -- no transformation is ever
auto-approved. Evaluation-linked records are rejected before a
transformation attempt is even made. See
docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.training_suitability_service import TrainingSuitabilityError
from core_model.training_incremental import (
    CANDIDATE_REVIEW_STATUSES,
    PROMOTABLE_SUITABILITY_STATUSES,
    TRANSFORMATION_TYPES,
)

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
                event_type=f"training_transformation_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="training_example_candidate",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("training_transformation_audit_write_failed", extra={"action": action})


def _checksum(prompt_text: str, assistant_text: str) -> str:
    return hashlib.sha256(f"{prompt_text}\n---\n{assistant_text}".encode()).hexdigest()


class TrainingExampleTransformationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def transform(
        self, item_public_id: str, values: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        item = self._training.get_item(item_public_id)
        if item["suitability_status"] not in PROMOTABLE_SUITABILITY_STATUSES:
            raise TrainingSuitabilityError(
                f"item is '{item['suitability_status']}' -- only "
                f"{', '.join(PROMOTABLE_SUITABILITY_STATUSES)} items may be transformed. "
                "Evaluation-only, RAG-only, not-suitable, and blocked records can never be "
                "transformed into training records."
            )
        transformation_type = values["transformation_type"]
        if transformation_type not in TRANSFORMATION_TYPES:
            raise TrainingSuitabilityError(f"unknown transformation_type: {transformation_type!r}")

        prompt_text = values.get("prompt_text", "")
        assistant_text = values.get("assistant_text", "")
        source_checksum = values["source_checksum"]
        candidate_checksum = _checksum(prompt_text, assistant_text)

        candidate = self._training.add_candidate(
            item_public_id,
            {
                "source_sample_record_public_id": values.get("source_sample_record_public_id"),
                "source_rag_sandbox_record_public_id": values.get(
                    "source_rag_sandbox_record_public_id"
                ),
                "transformation_type": transformation_type,
                "prompt_text": prompt_text,
                "assistant_text": assistant_text,
                "language": values.get("language", "unknown"),
                "task": values.get("task", ""),
                "source_checksum": source_checksum,
                "candidate_checksum": candidate_checksum,
                "transformation_version": values.get("transformation_version", "v1"),
            },
        )
        _audit(
            self._audit,
            action="transform",
            actor_reference=admin_id,
            resource_public_id=candidate["public_id"],
            outcome=AuditOutcome.SUCCESS,
            metadata={"transformation_type": transformation_type},
        )
        return candidate

    def review_candidate(
        self, candidate_public_id: str, values: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        decision = values["decision"]
        if decision not in CANDIDATE_REVIEW_STATUSES:
            raise TrainingSuitabilityError(f"unknown review decision: {decision!r}")
        if not values.get("reason", "").strip():
            raise TrainingSuitabilityError("a reason is required to review a training candidate")

        candidate = self._training.get_candidate(candidate_public_id)
        revised_prompt = values.get("revised_prompt_text")
        revised_assistant = values.get("revised_assistant_text")
        revised_checksum = None
        if revised_prompt is not None or revised_assistant is not None:
            new_prompt = revised_prompt if revised_prompt is not None else candidate["prompt_text"]
            new_assistant = (
                revised_assistant if revised_assistant is not None else candidate["assistant_text"]
            )
            revised_checksum = _checksum(new_prompt, new_assistant)

        self._training.add_revision(
            candidate_public_id,
            {
                "decision": decision,
                "reason": values["reason"],
                "revised_prompt_text": revised_prompt,
                "revised_assistant_text": revised_assistant,
                "revised_checksum": revised_checksum,
                "reviewer_admin_public_id": admin_id,
            },
        )

        if revised_checksum is not None:
            self._training.apply_revision_text(
                candidate_public_id,
                prompt_text=revised_prompt if revised_prompt is not None else candidate[
                    "prompt_text"
                ],
                assistant_text=(
                    revised_assistant if revised_assistant is not None else candidate[
                        "assistant_text"
                    ]
                ),
                candidate_checksum=revised_checksum,
            )

        # Ambiguous Tamil-correction transformations must remain
        # review-required -- never auto-approved even when a decision
        # string arrives, unless the reviewer explicitly chose
        # "approved" (a real human decision, not a default).
        review_status = "approved" if decision == "approved" else (
            "needs_revision" if decision == "needs_revision" else "rejected"
        )
        updated = self._training.review_candidate(
            candidate_public_id, review_status=review_status, reviewed_by=admin_id,
            conditions=values.get("conditions"),
        )
        _audit(
            self._audit,
            action="review_candidate",
            actor_reference=admin_id,
            resource_public_id=candidate_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"decision": decision},
        )
        return updated


__all__ = ["TrainingExampleTransformationService"]
