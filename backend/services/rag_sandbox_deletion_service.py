"""Phase 13 Step 26 governed expiry and deletion.

request -> impact preview -> Admin approval (`confirm`) -> execute
(archives the underlying sandbox `rag_knowledge_spaces` row via
`RagIngestionService.patch_space` -- the existing production lifecycle
mechanism, never a raw DELETE -- and marks the sandbox corpus/indexes
deleted) -> reports, acceptances, and audit are never touched. No
scheduler; every step is an explicit Admin action. See
docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.rag import RagRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.rag import KnowledgeSpacePatch
from backend.services.rag_ingestion_service import RagIngestionService
from backend.services.rag_sandbox_eligibility_service import RagSandboxError

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


class RagSandboxDeletionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._rag_repository = RagRepository(settings.resolved_database_path)
        self._ingestion = RagIngestionService(self._rag_repository, settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _impact_preview(self, experiment_public_id: str) -> dict[str, Any]:
        corpus = self._sandbox.get_corpus_for_experiment(experiment_public_id)
        indexes = self._sandbox.list_indexes(experiment_public_id)
        records = self._sandbox.list_records(experiment_public_id, limit=100, offset=0)
        reports = self._sandbox.list_reports(experiment_public_id)
        return {
            "corpus_public_id": corpus["public_id"] if corpus else None,
            "record_count": len(records),
            "index_count": len(indexes),
            "active_index_count": sum(1 for index in indexes if index["status"] == "active"),
            "reports_retained": len(reports),
            "note": "reports, acceptances, events, and audit history are retained after deletion",
        }

    def request_deletion(
        self, experiment_public_id: str, *, reason: str, admin_id: str
    ) -> dict[str, Any]:
        impact_preview = self._impact_preview(experiment_public_id)
        request = self._sandbox.request_deletion(
            experiment_public_id,
            {
                "reason": reason,
                "impact_preview": impact_preview,
                "requested_by_admin_public_id": admin_id,
            },
        )
        self._sandbox.record_event(
            experiment_public_id,
            {
                "event_type": "deletion_requested",
                "summary": reason,
                "metadata": impact_preview,
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="request_deletion",
            actor_reference=admin_id,
            resource_public_id=request["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return request

    def confirm_deletion(self, deletion_request_code: str, *, admin_id: str) -> dict[str, Any]:
        confirmed = self._sandbox.confirm_deletion(
            deletion_request_code, confirmed_by_admin_public_id=admin_id
        )
        _audit(
            self._audit,
            action="confirm_deletion",
            actor_reference=admin_id,
            resource_public_id=confirmed["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return confirmed

    def execute_deletion(self, deletion_request_code: str, *, admin_id: str) -> dict[str, Any]:
        latest = self._sandbox.get_latest_deletion_request_by_code(deletion_request_code)
        if latest is None or latest["status"] != "confirmed":
            raise RagSandboxError("deletion must be confirmed by an Admin before it can execute")

        corpus = self._sandbox.get_corpus_for_experiment(latest["experiment_public_id"])
        if corpus is not None:
            self._ingestion.patch_space(
                corpus["knowledge_space_public_id"],
                KnowledgeSpacePatch(lifecycle_status="archived"),
                admin_id,
            )
            self._sandbox.update_corpus(corpus["public_id"], {"status": "deleted"})
            for index in self._sandbox.list_indexes(latest["experiment_public_id"]):
                if index["status"] != "deleted":
                    self._sandbox.update_index(index["public_id"], {"status": "deleted"})

        executed = self._sandbox.execute_deletion(deletion_request_code)
        self._sandbox.update_experiment(latest["experiment_public_id"], {"status": "deleted"})
        self._sandbox.record_event(
            latest["experiment_public_id"],
            {
                "event_type": "deletion_executed",
                "summary": "sandbox corpus and indexes deleted; reports and audit retained",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="execute_deletion",
            actor_reference=admin_id,
            resource_public_id=executed["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return executed

    def cancel_deletion(self, deletion_request_code: str, *, admin_id: str) -> dict[str, Any]:
        cancelled = self._sandbox.cancel_deletion(deletion_request_code)
        self._sandbox.record_event(
            cancelled["experiment_public_id"],
            {
                "event_type": "deletion_cancelled",
                "summary": "deletion request cancelled",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="cancel_deletion",
            actor_reference=admin_id,
            resource_public_id=cancelled["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return cancelled


__all__ = ["RagSandboxDeletionService"]
