"""Phase 13 Step 22 query-level human review.

Append-only and attributed -- every review row is a fresh insert, never
an update, mirroring Phase 12's review-as-audit-trail pattern. See
docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.rag_sandbox_eligibility_service import RagSandboxError
from core_model.rag_sandbox import HUMAN_REVIEW_DECISIONS

logger = logging.getLogger(__name__)


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"rag_sandbox_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="rag_sandbox_experiment",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata={},
            )
        )
    except Exception:
        logger.exception("rag_sandbox_audit_write_failed", extra={"action": action})


class RagSandboxHumanReviewService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def review_query(
        self, experiment_public_id: str, query_public_id: str, values: dict[str, Any], *,
        admin_id: str,
    ) -> dict[str, Any]:
        decision = values["decision"]
        if decision not in HUMAN_REVIEW_DECISIONS:
            raise RagSandboxError(f"unknown human review decision: {decision!r}")
        review = self._sandbox.add_human_review(
            experiment_public_id,
            {
                "query_public_id": query_public_id,
                "answer_run_public_id": values.get("answer_run_public_id"),
                "retrieval_relevant": values.get("retrieval_relevant"),
                "answer_grounded": values.get("answer_grounded"),
                "citations_correct": values.get("citations_correct"),
                "language_appropriate": values.get("language_appropriate"),
                "refusal_correct": values.get("refusal_correct"),
                "conflict_handled": values.get("conflict_handled"),
                "injection_resisted": values.get("injection_resisted"),
                "decision": decision,
                "notes": values.get("notes", ""),
                "reviewer_admin_public_id": admin_id,
            },
        )
        self._sandbox.record_event(
            experiment_public_id,
            {
                "event_type": "human_review_recorded",
                "summary": f"query reviewed with decision '{decision}'",
                "metadata": {"query_public_id": query_public_id},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="review_query",
            actor_reference=admin_id,
            resource_public_id=review["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return review


__all__ = ["RagSandboxHumanReviewService"]
