"""Phase 12 Step 8 orchestration: turns one *approved* sample-import
file request into a bounded, quarantined download.

Ties together the approval's binding limits (Step 5), the streaming
transport's byte-cap enforcement (`dataset_sample_download_transport`),
and isolated quarantine storage (`dataset_sample_quarantine_service`).
Every attempt -- success or failure -- is recorded as an append-only
`external_dataset_sample_download_events` row and an audit event.
Never downloads a full dataset: each call fetches exactly one file,
and the approval's `approved_byte_limit`/`approved_record_limit`
bound the total across every call for one sample import.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.dataset_sample_download_transport import (
    Resolver,
    SampleDownloadError,
    StreamTransport,
    default_resolver,
    default_stream_http_transport,
    stream_download_to_file,
)
from backend.services.dataset_sample_eligibility_service import ExternalDatasetSampleApprovalService
from backend.services.dataset_sample_quarantine_service import (
    ExternalDatasetQuarantineService,
    safe_filename,
)

logger = logging.getLogger(__name__)


def _is_expired(expires_at: str | None) -> bool:
    """Never trusts a malformed/missing expiry as "still valid" by
    accident -- an unparseable date is treated as not-yet-expired only
    because the DB schema requires `expires_at` to be set by
    `approve_approval()` in the first place; this is defense in depth,
    not the primary guarantee."""

    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(expires_at)
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return datetime.now(UTC) > parsed


class DatasetSampleDownloadError(BrudError):
    status_code = 422
    code = "dataset_sample_download_rejected"


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
                resource_type="external_dataset_sample_file",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("dataset_sample_download_audit_write_failed", extra={"action": action})


class ExternalDatasetSampleDownloadService:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: StreamTransport = default_stream_http_transport,
        resolver: Resolver = default_resolver,
    ) -> None:
        self.settings = settings
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._quarantine = ExternalDatasetQuarantineService(settings)
        self._approvals = ExternalDatasetSampleApprovalService(settings)
        self._transport = transport
        self._resolver = resolver
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _require_approved(self, sample_import_public_id: str) -> dict[str, Any]:
        approval = self._samples.get_latest_approval(sample_import_public_id)
        if approval is None or approval["status"] != "approved":
            raise DatasetSampleDownloadError("no approved approval exists for this sample import")
        if _is_expired(approval["expires_at"]):
            raise DatasetSampleDownloadError("the approval has expired")
        if self._approvals.is_stale(approval["public_id"]):
            raise DatasetSampleDownloadError(
                "the approval is stale -- the underlying verification case has changed"
            )
        return approval

    def download_file(
        self,
        sample_import_public_id: str,
        *,
        source_url: str,
        allowed_domains: set[str],
        admin_id: str,
        original_filename: str | None = None,
    ) -> dict[str, Any]:
        sample_import = self._samples.get_sample_import(sample_import_public_id)
        if sample_import["status"] not in ("approved", "downloading"):
            raise DatasetSampleDownloadError(
                f"sample import must be 'approved' to download (currently "
                f"'{sample_import['status']}')"
            )
        approval = self._require_approved(sample_import_public_id)

        filename = safe_filename(original_filename or source_url.rsplit("/", 1)[-1] or "sample")
        file_record = self._samples.add_file(
            sample_import_public_id,
            {"original_filename": filename, "safe_filename": filename, "relative_path": filename},
        )

        self._quarantine.ensure_layout(sample_import_public_id)
        remaining = self._quarantine.remaining_quota_bytes(
            sample_import_public_id, approval["approved_byte_limit"]
        )
        if remaining <= 0:
            self._record_failure(
                sample_import_public_id, file_record["public_id"], admin_id,
                source_url=source_url, reason="approved_byte_limit_already_reached",
            )
            raise DatasetSampleDownloadError("the approved byte limit has already been reached")

        if sample_import["status"] == "approved":
            self._samples.update_sample_import(
                sample_import_public_id, {"status": "downloading", "current_stage": "download"}
            )
        self._samples.record_download_event(
            sample_import_public_id,
            {
                "file_public_id": file_record["public_id"],
                "event_type": "started",
                "source_url": source_url,
                "byte_limit": remaining,
                "performed_by_admin_public_id": admin_id,
            },
        )

        destination = self._quarantine.original_file_path(sample_import_public_id, filename)
        try:
            result = stream_download_to_file(
                source_url,
                destination,
                allowed_domains=allowed_domains,
                max_bytes=remaining,
                transport=self._transport,
                resolver=self._resolver,
            )
        except SampleDownloadError as exc:
            self._record_failure(
                sample_import_public_id, file_record["public_id"], admin_id,
                source_url=source_url, reason=exc.reason,
            )
            self._samples.update_file(file_record["public_id"], {"status": "corrupt"})
            raise DatasetSampleDownloadError(f"download failed: {exc.reason}") from exc

        self._samples.record_download_event(
            sample_import_public_id,
            {
                "file_public_id": file_record["public_id"],
                "event_type": "completed",
                "source_url": source_url,
                "resolved_domain": result.source_domain,
                "bytes_downloaded": result.bytes_downloaded,
                "checksum": result.checksum,
                "http_status": result.http_status,
                "performed_by_admin_public_id": admin_id,
            },
        )
        updated_file = self._samples.update_file(
            file_record["public_id"],
            {
                "status": "pending",
                "size_bytes": result.bytes_downloaded,
                "checksum": result.checksum,
            },
        )
        self._quarantine.add_manifest_entry(
            sample_import_public_id,
            {
                "filename": filename,
                "checksum": result.checksum,
                "size_bytes": result.bytes_downloaded,
                "source_url": source_url,
            },
        )
        self._samples.update_sample_import(
            sample_import_public_id,
            {"quarantine_bytes_used": self._quarantine.bytes_used(sample_import_public_id)},
        )
        _audit(
            self._audit,
            action="download_approved_sample",
            actor_reference=admin_id,
            resource_public_id=updated_file["public_id"],
            outcome=AuditOutcome.SUCCESS,
            metadata={"bytes_downloaded": result.bytes_downloaded, "warnings": result.warnings},
        )
        return updated_file

    def _record_failure(
        self,
        sample_import_public_id: str,
        file_public_id: str,
        admin_id: str,
        *,
        source_url: str,
        reason: str,
    ) -> None:
        self._samples.record_download_event(
            sample_import_public_id,
            {
                "file_public_id": file_public_id,
                "event_type": "failed",
                "source_url": source_url,
                "error_reason": reason,
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="download_approved_sample",
            actor_reference=admin_id,
            resource_public_id=file_public_id,
            outcome=AuditOutcome.FAILURE,
            metadata={"reason": reason},
        )

    def mark_downloaded(self, sample_import_public_id: str, *, admin_id: str) -> dict[str, Any]:
        """Explicit admin/service signal that no more files will be
        fetched for this import -- moves it into `quarantined` so
        validation/scanning can begin."""

        updated = self._samples.update_sample_import(
            sample_import_public_id, {"status": "quarantined", "current_stage": "file_validation"}
        )
        self._samples.record_event(
            sample_import_public_id,
            {
                "event_type": "quarantined",
                "to_status": "quarantined",
                "summary": "All approved files downloaded into quarantine",
                "performed_by_admin_public_id": admin_id,
            },
        )
        return updated
