"""Phase 12 Step 26 governed deletion of quarantined payloads.

Flow: request -> (show lineage impact) -> confirm -> execute (removes
payload files) -> manifest/checksums/reports/audit are always
retained. Each transition is its own append-only
`external_dataset_sample_deletion_requests` row (never an update to a
mutable status column), so the full deletion history survives even
after the underlying files are gone. No auto-cleanup scheduler exists
anywhere in this module -- deletion only ever happens via an explicit
Admin-confirmed request.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.dataset_sample_quarantine_service import ExternalDatasetQuarantineService

logger = logging.getLogger(__name__)


class DatasetSampleDeletionError(BrudError):
    status_code = 422
    code = "dataset_sample_deletion_rejected"


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
                resource_type="external_dataset_sample_deletion_request",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("dataset_sample_deletion_audit_write_failed", extra={"action": action})


class ExternalDatasetSampleDeletionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._quarantine = ExternalDatasetQuarantineService(settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _lineage_impact_summary(self, sample_import_public_id: str) -> dict[str, Any]:
        return {
            "files": len(self._samples.list_files(sample_import_public_id)),
            "records": len(self._samples.list_records(sample_import_public_id, limit=100)),
            "record_issues": len(self._samples.list_record_issues(sample_import_public_id)),
            "reviews": len(self._samples.list_reviews(sample_import_public_id)),
            "reports": len(self._samples.list_reports(sample_import_public_id)),
            "quarantine_bytes": self._quarantine.bytes_used(sample_import_public_id),
            "note": "manifest, checksums, reports, and audit history are always retained",
        }

    def request_deletion(
        self, sample_import_public_id: str, *, admin_id: str, reason: str
    ) -> dict[str, Any]:
        if not reason or not reason.strip():
            raise DatasetSampleDeletionError("a non-empty deletion reason is required")
        impact = self._lineage_impact_summary(sample_import_public_id)
        deletion_request = self._samples.request_deletion(
            sample_import_public_id,
            {
                "reason": reason,
                "requested_by_admin_public_id": admin_id,
                "lineage_impact_summary": impact,
            },
        )
        self._samples.record_event(
            sample_import_public_id,
            {
                "event_type": "deletion_requested",
                "summary": reason,
                "metadata": {"lineage_impact": impact},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="request_sample_deletion",
            actor_reference=admin_id,
            resource_public_id=deletion_request["public_id"],
            outcome=AuditOutcome.SUCCESS,
            metadata={"lineage_impact": impact},
        )
        return deletion_request

    def confirm_deletion(self, deletion_request_code: str, *, admin_id: str) -> dict[str, Any]:
        confirmed = self._samples.confirm_deletion(
            deletion_request_code, confirmed_by_admin_public_id=admin_id
        )
        _audit(
            self._audit,
            action="confirm_sample_deletion",
            actor_reference=admin_id,
            resource_public_id=confirmed["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return confirmed

    def execute_deletion(self, deletion_request_code: str, *, admin_id: str) -> dict[str, Any]:
        latest = self._samples.get_latest_deletion_request_by_code(deletion_request_code)
        if latest is None or latest["status"] != "confirmed":
            raise DatasetSampleDeletionError(
                "deletion must be confirmed by an admin before it can be executed"
            )
        sample_import_public_id = latest["sample_import_public_id"]
        self._quarantine.delete_payload(sample_import_public_id)
        self._samples.mark_sample_import_deleted(sample_import_public_id)
        executed = self._samples.execute_deletion(deletion_request_code)
        self._samples.record_event(
            sample_import_public_id,
            {
                "event_type": "deletion_executed",
                "to_status": "deleted",
                "summary": f"Quarantined payload deleted by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="execute_sample_deletion",
            actor_reference=admin_id,
            resource_public_id=executed["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return executed

    def cancel_deletion(self, deletion_request_code: str, *, admin_id: str) -> dict[str, Any]:
        cancelled = self._samples.cancel_deletion(deletion_request_code)
        self._samples.record_event(
            cancelled["sample_import_public_id"],
            {
                "event_type": "deletion_cancelled",
                "summary": f"Deletion request cancelled by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="cancel_sample_deletion",
            actor_reference=admin_id,
            resource_public_id=cancelled["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return cancelled
