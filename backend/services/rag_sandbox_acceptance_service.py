"""Phase 13 Step 24 Admin acceptance -- separate from report
finalization.

Acceptance never activates production RAG, never approves training,
and is rejected as stale if the report it targets is no longer the
experiment's latest report or if the underlying Phase 12 sample data
has changed since approval. See
docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.rag_sandbox_eligibility_service import (
    RagSandboxApprovalService,
    RagSandboxError,
)
from core_model.rag_sandbox import ACCEPTANCE_DECISIONS

logger = logging.getLogger(__name__)

_STATUS_BY_DECISION = {
    "accepted": "accepted",
    "accepted_with_conditions": "accepted_with_conditions",
    "rejected": "rejected",
    "needs_more_testing": "needs_review",
}


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


class RagSandboxAcceptanceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._approval_service = RagSandboxApprovalService(settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def decide(
        self,
        experiment_public_id: str,
        *,
        decision: str,
        reason: str,
        report_public_id: str,
        admin_id: str,
        conditions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if decision not in ACCEPTANCE_DECISIONS:
            raise RagSandboxError(f"unknown acceptance decision: {decision!r}")
        if not reason or not reason.strip():
            raise RagSandboxError("a reason is required for every acceptance decision")

        latest_report = self._sandbox.get_latest_report(experiment_public_id)
        if latest_report is None:
            raise RagSandboxError("no finalized report exists for this experiment yet")
        if latest_report["public_id"] != report_public_id:
            raise RagSandboxError(
                "the report has changed since this acceptance decision was prepared -- "
                "reload the latest report before deciding"
            )

        approval = self._sandbox.get_latest_approval(experiment_public_id)
        if approval and self._approval_service.is_stale(approval["public_id"]):
            raise RagSandboxError(
                "the underlying Phase 12 sample report or accepted-record set has changed "
                "since approval -- this acceptance decision is stale"
            )

        acceptance = self._sandbox.add_acceptance(
            experiment_public_id,
            {
                "report_public_id": report_public_id,
                "decision": decision,
                "reason": reason,
                "conditions": conditions or {},
                "reviewer_admin_public_id": admin_id,
                "report_checksum_sha256": latest_report["report_checksum_sha256"],
                "target_fingerprint": approval["target_fingerprint"] if approval else "",
            },
        )
        new_status = _STATUS_BY_DECISION[decision]
        self._sandbox.update_experiment(
            experiment_public_id, {"status": new_status, "current_stage": "acceptance"}
        )
        self._sandbox.record_event(
            experiment_public_id,
            {
                "event_type": "accepted" if decision != "rejected" else "rejected",
                "to_status": new_status,
                "summary": f"Admin acceptance decision: {decision}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="accept",
            actor_reference=admin_id,
            resource_public_id=acceptance["public_id"],
            outcome=AuditOutcome.SUCCESS,
            metadata={"decision": decision},
        )
        return acceptance

    def get_latest_acceptance(self, experiment_public_id: str) -> dict[str, Any] | None:
        return self._sandbox.get_latest_acceptance(experiment_public_id)


__all__ = ["RagSandboxAcceptanceService"]
