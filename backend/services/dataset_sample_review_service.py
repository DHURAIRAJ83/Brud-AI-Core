"""Phase 12 Step 22 human review workflow.

Every review decision is an append-only
`external_dataset_sample_reviews` row (mirrors Phase 11's
`_verification_reviews` pattern exactly). `edit_derived_copy`/
`redact_derived_copy` decisions carry the new derived text directly on
that same append-only row -- each edit is already its own immutable
version, so no separate "derived revisions" table is needed, and the
original file/record this review targets is never touched by any
review row. Reviewing a `record_issue` also updates that issue's own
queryable `reviewer_decision`/`reviewed_by`/`review_reason` columns
(via the repository's `review_record_issue`) so list/filter views don't
need to replay the whole append-only log to know an issue's current
state -- the append-only row remains the authoritative history either
way.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from core_model.sample_import import DERIVED_REVISION_REVIEW_DECISIONS, REVIEW_DECISIONS

logger = logging.getLogger(__name__)


class DatasetSampleReviewError(BrudError):
    status_code = 422
    code = "dataset_sample_review_rejected"


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
                event_type=f"dataset_sample_import_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="external_dataset_sample_review",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("dataset_sample_review_audit_write_failed", extra={"action": action})


class ExternalDatasetSampleReviewService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _validate(
        self, *, decision: str, reason: str, derived_content_text: str | None
    ) -> None:
        if decision not in REVIEW_DECISIONS:
            raise DatasetSampleReviewError(f"'{decision}' is not a recognized review decision")
        if not reason or not reason.strip():
            raise DatasetSampleReviewError("a non-empty review reason is required")
        if derived_content_text is not None and decision not in DERIVED_REVISION_REVIEW_DECISIONS:
            raise DatasetSampleReviewError(
                f"derived content may only be supplied for decisions in "
                f"{DERIVED_REVISION_REVIEW_DECISIONS}"
            )

    def review_target(
        self,
        sample_import_public_id: str,
        *,
        target_type: str,
        target_id: str | None,
        decision: str,
        reason: str,
        reviewer_admin_public_id: str,
        derived_content_text: str | None = None,
        conditions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._validate(decision=decision, reason=reason, derived_content_text=derived_content_text)
        derived_checksum = (
            hashlib.sha256(derived_content_text.encode("utf-8")).hexdigest()
            if derived_content_text is not None
            else None
        )
        review = self._samples.add_review(
            sample_import_public_id,
            {
                "target_type": target_type,
                "target_id": target_id,
                "decision": decision,
                "reason": reason,
                "derived_content_text": derived_content_text,
                "derived_content_checksum": derived_checksum,
                "conditions": conditions or {},
                "reviewer_admin_public_id": reviewer_admin_public_id,
            },
        )
        if target_type == "issue" and target_id is not None:
            self._samples.review_record_issue(
                target_id,
                reviewer_decision=decision,
                reviewed_by=reviewer_admin_public_id,
                review_reason=reason,
            )
        self._samples.record_event(
            sample_import_public_id,
            {
                "event_type": "review_recorded",
                "summary": f"{target_type} reviewed: {decision}",
                "metadata": {"target_id": target_id, "decision": decision},
                "performed_by_admin_public_id": reviewer_admin_public_id,
            },
        )
        _audit(
            self._audit,
            action="review_sample_issue",
            actor_reference=reviewer_admin_public_id,
            resource_public_id=review["public_id"],
            outcome=AuditOutcome.SUCCESS,
            metadata={"target_type": target_type, "decision": decision},
        )
        return review

    def list_reviews(self, sample_import_public_id: str) -> list[dict[str, Any]]:
        return self._samples.list_reviews(sample_import_public_id)
