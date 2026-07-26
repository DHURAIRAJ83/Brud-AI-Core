"""Governed Admin Assistant.

The assistant is read-only by default: it summarizes dashboard state and
drafts proposals. It never mutates anything itself. A mutation only
happens when an admin reviews a pending proposal through Admin Review and
approves it, and even then execution is dispatched through an allowlisted
existing service call -- never a bespoke write path -- so every mutation
still passes through the same validation, transitions, and audit hooks it
would if an admin had performed it by hand in the dashboard.

Every step (proposal created, reviewed, executed, failed) is written to
the audit log via AuditLogRepository so the whole lifecycle is traceable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.connection import database_connection
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.phase2 import AdminApprovalRepository
from backend.models.datasets import SourcePatch
from backend.models.domain import (
    AdminApprovalCreate,
    AdminApprovalPublic,
    AuditEventCreate,
    AuditOutcome,
    ReviewDecision,
)
from backend.services.dataset_service import DatasetService

logger = logging.getLogger(__name__)


# Action types the assistant is allowed to propose. Each maps to a callable
# that performs the mutation through an existing, already-secured admin
# service -- the assistant never talks to the database directly for writes.
# Anything not in this map cannot be proposed or executed, which is also
# what keeps training out of reach: there is no "start_training" entry and
# there never should be one added here.
ActionExecutor = Callable[[Path, str, dict[str, Any], str], dict[str, Any]]


def _execute_dataset_record_review(
    database_path: Path, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    service = DatasetService(DatasetAdminRepository(database_path))
    decision = ReviewDecision(payload["decision"])
    comments = payload.get("comments")
    return service.review(target_public_id, decision, comments, admin_id)


def _execute_dataset_source_update(
    database_path: Path, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    service = DatasetService(DatasetAdminRepository(database_path))
    patch = SourcePatch.model_validate(payload)
    return service.update_source(target_public_id, patch, admin_id)


ACTION_EXECUTORS: dict[str, ActionExecutor] = {
    "dataset_record_review": _execute_dataset_record_review,
    "dataset_source_update": _execute_dataset_source_update,
}

# Defense in depth: even if a future action executor is registered above,
# refuse to run anything whose name suggests it starts or resumes a
# training run. The Admin Assistant must never start model training.
_BLOCKED_ACTION_SUBSTRINGS = ("train", "pretrain")


class AdminAssistantError(BrudError):
    """Raised for governance violations (unknown/blocked action, bad state)."""

    status_code = 422
    code = "admin_assistant_rejected"


class AdminAssistantService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database_path = settings.resolved_database_path
        self.approvals = AdminApprovalRepository(self.database_path)
        self._audit = (
            AuditLogRepository(self.database_path) if settings.audit_enabled else None
        )

    # -- audit -------------------------------------------------------

    def _record_audit(
        self,
        *,
        event_type: str,
        action: str,
        actor_reference: str | None,
        resource_public_id: str | None,
        outcome: AuditOutcome,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._audit:
            return
        try:
            self._audit.append(
                AuditEventCreate(
                    event_type=event_type,
                    actor_type="admin_assistant",
                    actor_reference=actor_reference,
                    action=action,
                    resource_type="admin_approval",
                    resource_public_id=resource_public_id,
                    outcome=outcome,
                    metadata=metadata or {},
                )
            )
        except Exception:
            logger.exception("admin_assistant_audit_write_failed", extra={"action": action})

    # -- dashboard understanding (read-only) --------------------------

    def dashboard_overview(self) -> dict[str, Any]:
        """Summarize the state of every governed area of the Admin Dashboard.

        Purely read-only: counts and status breakdowns the assistant uses
        to explain "what needs attention" and to guide the admin step by
        step. Never mutates anything.
        """

        with database_connection(self.database_path) as connection:

            def counts_by(table: str, column: str = "status") -> dict[str, int]:
                rows = connection.execute(
                    f"SELECT {column} AS bucket, COUNT(*) AS n FROM {table} GROUP BY {column}"
                ).fetchall()
                return {row["bucket"]: row["n"] for row in rows}

            def table_exists(table: str) -> bool:
                return bool(
                    connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone()
                )

            overview: dict[str, Any] = {
                "dataset_sources": counts_by("dataset_sources"),
                "dataset_records": counts_by("dataset_records"),
                "training_jobs": counts_by("training_jobs"),
                "model_registry": counts_by("model_registry", "status"),
                "user_feedback": counts_by("user_feedback"),
                "admin_approvals": counts_by("admin_approvals"),
            }
            if table_exists("corpus_releases"):
                overview["corpus_releases"] = counts_by("corpus_releases")
            if table_exists("model_versions"):
                overview["model_versions"] = counts_by("model_versions", "lifecycle_status")

        pending_review = overview["dataset_records"].get("pending_review", 0)
        pending_approvals = overview["admin_approvals"].get("pending", 0)
        guidance: list[str] = []
        if pending_review:
            guidance.append(
                f"{pending_review} dataset record(s) are pending_review -- inspect and either "
                "propose approve/reject decisions."
            )
        if pending_approvals:
            guidance.append(
                f"{pending_approvals} Admin Assistant proposal(s) are awaiting Admin Review "
                "before they can execute."
            )
        if not guidance:
            guidance.append("No pending dataset reviews or proposals right now.")

        return {"summary": overview, "guidance": guidance}

    # -- proposals -----------------------------------------------------

    def propose(
        self,
        *,
        action_type: str,
        target_type: str,
        target_public_id: str,
        request_payload: dict[str, Any],
        requested_by: str,
        summary: str,
    ) -> AdminApprovalPublic:
        if action_type not in ACTION_EXECUTORS:
            raise AdminAssistantError(f"unsupported action_type: {action_type}")
        if any(token in action_type.lower() for token in _BLOCKED_ACTION_SUBSTRINGS):
            raise AdminAssistantError(f"action_type is not permitted: {action_type}")
        proposal = self.approvals.create(
            AdminApprovalCreate(
                action_type=action_type,
                target_type=target_type,
                target_public_id=target_public_id,
                request_payload=request_payload,
                requested_by=requested_by,
                summary=summary,
            )
        )
        self._record_audit(
            event_type="admin_assistant_proposal_created",
            action=action_type,
            actor_reference=requested_by,
            resource_public_id=proposal.public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"target_type": target_type, "target_public_id": target_public_id},
        )
        return proposal

    def list_proposals(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[AdminApprovalPublic]:
        return self.approvals.list(status=status, limit=limit, offset=offset)

    def get_proposal(self, public_id: str) -> AdminApprovalPublic:
        return self.approvals.get_by_public_id(public_id)

    # -- Admin Review: approve / reject --------------------------------

    def review(
        self,
        public_id: str,
        *,
        decision: str,
        reviewed_by: str,
        comment: str | None,
    ) -> AdminApprovalPublic:
        if decision not in {"approved", "rejected"}:
            raise AdminAssistantError(f"unsupported review decision: {decision}")
        try:
            result = self.approvals.update_review(
                public_id, status=decision, reviewed_by=reviewed_by, review_comment=comment
            )
        except (NotFoundError, ValidationError) as exc:
            self._record_audit(
                event_type="admin_review_decision_failed",
                action=decision,
                actor_reference=reviewed_by,
                resource_public_id=public_id,
                outcome=AuditOutcome.FAILURE,
                metadata={"error": str(exc)},
            )
            raise
        self._record_audit(
            event_type=f"admin_review_{decision}",
            action=decision,
            actor_reference=reviewed_by,
            resource_public_id=public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"comment": comment} if comment else {},
        )
        return result

    # -- execution: approved proposals only, via existing services -----

    def execute(self, public_id: str, *, executor_public_id: str) -> AdminApprovalPublic:
        proposal = self.approvals.get_by_public_id(public_id)
        if proposal.status != "approved":
            raise AdminAssistantError(
                f"proposal must be approved before execution (status={proposal.status})"
            )
        executor = ACTION_EXECUTORS.get(proposal.action_type)
        if executor is None or any(
            token in proposal.action_type.lower() for token in _BLOCKED_ACTION_SUBSTRINGS
        ):
            self._fail_execution(proposal, executor_public_id, "action_type not permitted")
            raise AdminAssistantError(f"action_type not permitted: {proposal.action_type}")
        try:
            result = executor(
                self.database_path,
                proposal.target_public_id,
                proposal.request_payload,
                executor_public_id,
            )
        except Exception as exc:
            self._fail_execution(proposal, executor_public_id, str(exc))
            raise
        updated = self.approvals.update_execution(
            public_id,
            execution_status="succeeded",
            execution_result=result,
            executor_public_id=executor_public_id,
        )
        self._record_audit(
            event_type="admin_assistant_proposal_executed",
            action=proposal.action_type,
            actor_reference=executor_public_id,
            resource_public_id=public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"target_public_id": proposal.target_public_id},
        )
        return updated

    def _fail_execution(
        self, proposal: AdminApprovalPublic, executor_public_id: str, error: str
    ) -> None:
        try:
            self.approvals.update_execution(
                proposal.public_id,
                execution_status="failed",
                execution_result={"error": error},
                executor_public_id=executor_public_id,
            )
        except (NotFoundError, ValidationError):
            logger.exception("admin_assistant_execution_failure_write_failed")
        self._record_audit(
            event_type="admin_assistant_proposal_execution_failed",
            action=proposal.action_type,
            actor_reference=executor_public_id,
            resource_public_id=proposal.public_id,
            outcome=AuditOutcome.FAILURE,
            metadata={"error": error, "target_public_id": proposal.target_public_id},
        )
