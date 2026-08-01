"""Phase 13 Step 10 query-set model: Admin-authored, assistant-
suggested, multilingual, adversarial, insufficient-evidence, and
conflict query sets bound to one sandbox experiment.

A query set is mutable while `draft` and immutable once `finalized`
(schema-level trigger). Assistant-suggested queries (`human_authored`
false) require an explicit Admin review before finalize succeeds --
enforced here, not just documented. See
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
from core_model.rag_sandbox import QUERY_LANGUAGES, QUERY_TYPES

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
                event_type=f"rag_sandbox_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="rag_sandbox_experiment",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("rag_sandbox_audit_write_failed", extra={"action": action})


class RagSandboxQuerySetService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def create_query_set(
        self, experiment_public_id: str, *, name: str, admin_id: str
    ) -> dict[str, Any]:
        query_set = self._sandbox.create_query_set(
            experiment_public_id, {"name": name, "created_by_admin_public_id": admin_id}
        )
        self._sandbox.record_event(
            experiment_public_id,
            {
                "event_type": "query_set_created",
                "summary": f"query set '{name}' created",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="create_query_set",
            actor_reference=admin_id,
            resource_public_id=query_set["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return query_set

    def add_query(
        self, query_set_public_id: str, values: dict[str, Any], *, created_by: str
    ) -> dict[str, Any]:
        if values["query_type"] not in QUERY_TYPES:
            raise RagSandboxError(f"unknown query_type: {values['query_type']!r}")
        language = values.get("language", "unknown")
        if language not in QUERY_LANGUAGES:
            raise RagSandboxError(f"unknown query language: {language!r}")
        return self._sandbox.add_query(
            query_set_public_id,
            {
                "query_text": values["query_text"],
                "language": language,
                "query_type": values["query_type"],
                "expected_source_ids": values.get("expected_source_ids", []),
                "expected_answer_notes": values.get("expected_answer_notes", ""),
                "must_refuse_if_insufficient": values.get("must_refuse_if_insufficient", False),
                "conflict_expected": values.get("conflict_expected", False),
                "injection_test": values.get("injection_test", False),
                "human_authored": values.get("human_authored", True),
                "created_by": created_by,
            },
        )

    def review_query(self, query_public_id: str, *, admin_id: str) -> dict[str, Any]:
        return self._sandbox.review_query(query_public_id, reviewed_by_admin_public_id=admin_id)

    def finalize_query_set(self, query_set_public_id: str, *, admin_id: str) -> dict[str, Any]:
        unreviewed = self._sandbox.count_unreviewed_assistant_queries(query_set_public_id)
        if unreviewed:
            raise RagSandboxError(
                f"{unreviewed} assistant-suggested quer{'y' if unreviewed == 1 else 'ies'} "
                "must be reviewed before this query set can be finalized"
            )
        query_set = self._sandbox.finalize_query_set(
            query_set_public_id, finalized_by_admin_public_id=admin_id
        )
        self._sandbox.record_event(
            query_set["experiment_public_id"],
            {
                "event_type": "query_set_finalized",
                "summary": f"query set '{query_set['name']}' finalized",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="finalize_query_set",
            actor_reference=admin_id,
            resource_public_id=query_set_public_id,
            outcome=AuditOutcome.SUCCESS,
        )
        return query_set


__all__ = ["RagSandboxQuerySetService"]
