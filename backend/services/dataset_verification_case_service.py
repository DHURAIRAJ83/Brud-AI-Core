"""Phase 11 Step 4/20/22: the verification case lifecycle owner.
`draft -> collecting_evidence -> needs_review -> in_review ->
(verified | verified_with_conditions | insufficient_evidence |
conflicting_evidence | blocked) | cancelled | expired | withdrawn`.
Every transition is an `external_dataset_verification_events` row.

Enforces Step 22's "only one active verification case per candidate
unless explicitly versioned" as a service-level guard (the repository
itself has no DB constraint for it, since "explicitly versioned" is a
human judgment call, not a structural rule)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.models.domain import AuditEventCreate, AuditOutcome

logger = logging.getLogger(__name__)


class DatasetVerificationCaseError(BrudError):
    status_code = 422
    code = "dataset_verification_case_rejected"


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    event_type: str,
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
                event_type=event_type,
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="external_dataset_verification_case",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("dataset_verification_case_audit_write_failed", extra={"action": action})


class ExternalDatasetVerificationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DatasetVerificationRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def create_case(
        self,
        *,
        candidate_public_id: str,
        admin_id: str,
        search_session_public_id: str | None = None,
        verification_scope: str = "",
        force_new_version: bool = False,
    ) -> dict[str, Any]:
        if not force_new_version:
            active = self.repository.get_active_case_for_candidate(candidate_public_id)
            if active is not None:
                raise DatasetVerificationCaseError(
                    "an active verification case already exists for this candidate "
                    f"({active['public_id']}); pass force_new_version to create another"
                )
        verification_code = f"VC-{uuid4().hex[:16]}"
        case = self.repository.create_case(
            {
                "candidate_public_id": candidate_public_id,
                "search_session_public_id": search_session_public_id,
                "verification_code": verification_code,
                "verification_scope": verification_scope,
                "requested_by_admin_public_id": admin_id,
            }
        )
        self.repository.record_event(
            case["public_id"],
            {
                "event_type": "case_created",
                "summary": f"Verification case created for candidate {candidate_public_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_case_created",
            action="create_case",
            actor_reference=admin_id,
            resource_public_id=case["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return case

    def get_case(self, case_public_id: str) -> dict[str, Any]:
        return self.repository.get_case(case_public_id)

    def list_cases(self, **filters: Any) -> list[dict[str, Any]]:
        return self.repository.list_cases(**filters)

    def overview(self) -> dict[str, int]:
        return self.repository.overview_counts()

    def start(self, case_public_id: str, *, admin_id: str) -> dict[str, Any]:
        case = self.repository.get_case(case_public_id)
        if case["status"] != "draft":
            raise DatasetVerificationCaseError(
                f"case can only be started from 'draft' (currently '{case['status']}')"
            )
        updated = self.repository.update_case(
            case_public_id, {"status": "collecting_evidence", "started_at": _now_sql_timestamp()}
        )
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "evidence_collected",
                "summary": "Verification started -- collecting evidence",
                "performed_by_admin_public_id": admin_id,
            },
        )
        return updated

    def cancel(self, case_public_id: str, *, admin_id: str) -> dict[str, Any]:
        case = self.repository.get_case(case_public_id)
        if case["locked_at"] is not None:
            raise DatasetVerificationCaseError("cannot cancel an already-finalized case")
        updated = self.repository.update_case(
            case_public_id, {"status": "cancelled", "cancelled_at": _now_sql_timestamp()}
        )
        self.repository.record_event(
            case_public_id,
            {
                "event_type": "case_cancelled",
                "summary": f"Cancelled by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            event_type="dataset_verification_case_cancelled",
            action="cancel_case",
            actor_reference=admin_id,
            resource_public_id=case_public_id,
            outcome=AuditOutcome.SUCCESS,
        )
        return updated


def _now_sql_timestamp() -> str:
    """Matches SQLite's own `CURRENT_TIMESTAMP` format (UTC,
    `YYYY-MM-DD HH:MM:SS`)."""

    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
