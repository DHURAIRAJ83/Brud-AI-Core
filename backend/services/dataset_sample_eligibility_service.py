"""Phase 12 Step 6 eligibility gate and Step 5 sample-import approval.

Reads Phase 11's verification case (read-only) and the Provider
Registry (read-only) to decide whether a bounded sample-import
proposal may even be created, then owns the separate, explicitly
bound approval record a human Admin must sign off on before any byte
is downloaded. Never mutates a Phase 11 verification case or a
provider row. See
docs/sample_import/phase12_sample_import_quarantine_plan.md.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import NotFoundError
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_data_providers import ExternalDataProviderRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from core_model.data_providers import is_usable_for_discovery
from core_model.data_verification import STRONG_IDENTITY_STATUSES
from core_model.sample_import import validate_sample_import_purpose

logger = logging.getLogger(__name__)


class DatasetSampleImportError(BrudError):
    status_code = 422
    code = "dataset_sample_import_rejected"


_RELEVANT_PERMISSION_BY_PURPOSE = {"rag_sandbox_preparation": "rag_use"}
_DEFAULT_RELEVANT_PERMISSION = "evaluation_use"
_DENIED_PERMISSION_STATUSES = ("not_approved", "prohibited")


def compute_target_fingerprint(
    case: dict[str, Any], *, dataset_version: str | None, revision: str | None
) -> str:
    """A stable digest of every case-level fact a bound approval must
    stay pinned to -- if any of these change after approval, a freshly
    computed fingerprint stops matching the approval's own stored one,
    and the download is rejected as stale (Step 5/8). Deliberately pure
    (no I/O) so both the approval service and the Admin Assistant's
    `STALE_CHECK_FINGERPRINTS` registry can call it identically."""

    payload = {
        "case_status": case["status"],
        "verification_expiry_status": case["verification_expiry_status"],
        "declared_licence": case["declared_licence"],
        "normalized_licence_identifier": case["normalized_licence_identifier"],
        "dataset_version": dataset_version,
        "revision": revision,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


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
                resource_type="external_dataset_sample_import",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("dataset_sample_import_audit_write_failed", extra={"action": action})


class ExternalDatasetSampleEligibilityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._verification = DatasetVerificationRepository(settings.resolved_database_path)
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._providers = ExternalDataProviderRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    @staticmethod
    def _relevant_permission_type(purpose: str) -> str:
        return _RELEVANT_PERMISSION_BY_PURPOSE.get(purpose, _DEFAULT_RELEVANT_PERMISSION)

    def check_eligibility(
        self,
        case_public_id: str,
        *,
        purpose: str,
        provider_public_id: str | None = None,
        dataset_version: str | None = None,
        revision: str | None = None,
    ) -> dict[str, Any]:
        """Every check from Step 6, run read-only. Never raises for a
        blocked outcome -- callers decide whether to surface it as an
        error (`create_sample_import`) or just display it. A prohibited/
        unrecognized purpose is the one exception: it is a malformed
        request, not a soft eligibility signal, so it raises immediately
        as a `DatasetSampleImportError` (never a bare `ValueError`,
        which the API layer's registered exception handler would not
        recognize)."""

        try:
            validate_sample_import_purpose(purpose)
        except ValueError as exc:
            raise DatasetSampleImportError(str(exc)) from exc
        case = self._verification.get_case(case_public_id)
        checks: dict[str, dict[str, Any]] = {}
        blocking_reasons: list[str] = []
        warnings: list[str] = []

        finalized = case["locked_at"] is not None
        checks["verification_case_finalized"] = {"passed": finalized}
        if not finalized:
            blocking_reasons.append("Phase 11 verification case is not yet finalized")

        identity_ok = case["identity_status"] in STRONG_IDENTITY_STATUSES
        checks["identity_sufficiently_verified"] = {
            "passed": identity_ok, "identity_status": case["identity_status"],
        }
        if not identity_ok:
            blocking_reasons.append(
                f"dataset identity status '{case['identity_status']}' is not strong enough"
            )

        expiry_ok = case["verification_expiry_status"] not in (
            "expired", "source_changed", "withdrawn",
        )
        checks["verification_current_and_evidence_unchanged"] = {
            "passed": expiry_ok, "verification_expiry_status": case["verification_expiry_status"],
        }
        if not expiry_ok:
            blocking_reasons.append(
                f"verification expiry status is '{case['verification_expiry_status']}' -- "
                "reverify before requesting a sample"
            )

        withdrawal_notices = self._verification.list_withdrawal_notices(case_public_id)
        no_withdrawal = len(withdrawal_notices) == 0
        checks["no_active_withdrawal_notice"] = {
            "passed": no_withdrawal, "notice_count": len(withdrawal_notices),
        }
        if not no_withdrawal:
            blocking_reasons.append(
                "an active withdrawal notice blocks new sample imports for this dataset"
            )

        upstream_ok = not self._verification.unresolved_upstream_exists(case_public_id)
        checks["upstream_blockers_resolved"] = {"passed": upstream_ok}
        if not upstream_ok:
            blocking_reasons.append("one or more upstream sources are not yet verified")

        permission_type = self._relevant_permission_type(purpose)
        permission = self._verification.get_permission_assessment(case_public_id, permission_type)
        permission_status = permission["status"] if permission else "unknown"
        permission_ok = permission_status not in _DENIED_PERMISSION_STATUSES
        checks["relevant_permission_eligible"] = {
            "passed": permission_ok,
            "permission_type": permission_type,
            "status": permission_status,
        }
        checks["sample_import_not_prohibited"] = {"passed": permission_ok}
        if not permission_ok:
            blocking_reasons.append(
                f"'{permission_type}' permission is '{permission_status}' for this dataset"
            )

        commercial = self._verification.get_permission_assessment(case_public_id, "commercial_use")
        checks["commercial_restriction_understood"] = {
            "passed": True, "status": commercial["status"] if commercial else "not_assessed",
        }
        if not commercial:
            warnings.append("commercial-use permission has not yet been assessed for this dataset")

        provider_ok = True
        if provider_public_id:
            try:
                provider = self._providers.get_provider(provider_public_id)
            except NotFoundError:
                provider_ok = False
                blocking_reasons.append("provider not found")
            else:
                provider_ok = is_usable_for_discovery(
                    lifecycle_status=provider["lifecycle_status"], enabled=provider["enabled"]
                )
                if not provider_ok:
                    blocking_reasons.append("provider is disabled or in a blocked lifecycle state")
        checks["provider_enabled_and_not_blocked"] = {"passed": provider_ok}

        version_pinned = bool(dataset_version) or bool(revision)
        checks["dataset_version_or_revision_pinned"] = {"passed": version_pinned}
        if not version_pinned:
            warnings.append(
                "no dataset_version or revision was pinned -- reproducibility cannot be guaranteed"
            )

        return {
            "eligible": len(blocking_reasons) == 0,
            "checks": checks,
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
            "case": case,
        }

    def create_sample_import(self, case_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        """The one entry point that turns an eligibility pass into a
        real `draft` sample-import row -- refuses outright if the gate
        is not clear. Never downloads anything and never activates
        RAG; this only opens the case for a bounded, still-unapproved
        sample-import proposal (Step 6)."""

        purpose = values["purpose"]
        result = self.check_eligibility(
            case_public_id,
            purpose=purpose,
            provider_public_id=values.get("provider_public_id"),
            dataset_version=values.get("dataset_version"),
            revision=values.get("revision"),
        )
        if not result["eligible"]:
            raise DatasetSampleImportError(
                "sample import is not eligible: " + "; ".join(result["blocking_reasons"])
            )
        case = result["case"]
        admin_id = values["requested_by_admin_public_id"]
        sample_import = self._samples.create_sample_import(
            {
                "sample_import_code": values.get("sample_import_code") or f"SI-{uuid4().hex[:16]}",
                "verification_case_public_id": case_public_id,
                "candidate_public_id": case["candidate_public_id"],
                "provider_public_id": values.get("provider_public_id"),
                "purpose": purpose,
                "dataset_version": values.get("dataset_version"),
                "revision": values.get("revision"),
                "selection_method": values["selection_method"],
                "selection_seed": values.get("selection_seed"),
                "source_split": values.get("source_split"),
                "source_file": values.get("source_file"),
                "row_start": values.get("row_start"),
                "row_end": values.get("row_end"),
                "requested_count": values.get("requested_count", 0),
                "expected_modality": values.get("expected_modality", "text"),
                "requested_by_admin_public_id": admin_id,
            }
        )
        self._samples.record_event(
            sample_import["public_id"],
            {
                "event_type": "import_created",
                "to_status": "draft",
                "summary": f"Sample import proposal created for purpose '{purpose}'",
                "metadata": {"warnings": result["warnings"]},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="create_sample_import",
            actor_reference=admin_id,
            resource_public_id=sample_import["public_id"],
            outcome=AuditOutcome.SUCCESS,
            metadata={"purpose": purpose, "warnings": result["warnings"]},
        )
        return sample_import

    def get_case_for_import(self, sample_import_public_id: str) -> dict[str, Any]:
        sample_import = self._samples.get_sample_import(sample_import_public_id)
        return self._verification.get_case(sample_import["verification_case_public_id"])


class ExternalDatasetSampleApprovalService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._verification = DatasetVerificationRepository(settings.resolved_database_path)
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _current_fingerprint(self, sample_import: dict[str, Any]) -> str:
        case = self._verification.get_case(sample_import["verification_case_public_id"])
        return compute_target_fingerprint(
            case,
            dataset_version=sample_import["dataset_version"],
            revision=sample_import["revision"],
        )

    def request_approval(
        self, sample_import_public_id: str, values: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        sample_import = self._samples.get_sample_import(sample_import_public_id)
        if sample_import["purpose"] != values.get("purpose", sample_import["purpose"]):
            raise DatasetSampleImportError(
                "approval purpose must match the sample import's purpose"
            )
        fingerprint = self._current_fingerprint(sample_import)
        approval = self._samples.create_approval(
            sample_import_public_id,
            {
                "verification_case_public_id": sample_import["verification_case_public_id"],
                "candidate_public_id": sample_import["candidate_public_id"],
                "provider_public_id": sample_import.get("provider_public_id"),
                "purpose": sample_import["purpose"],
                "requested_record_limit": values["requested_record_limit"],
                "requested_byte_limit": values["requested_byte_limit"],
                "allowed_file_ids": values.get("allowed_file_ids", []),
                "allowed_file_patterns": values.get("allowed_file_patterns", []),
                "allowed_formats": values.get("allowed_formats", []),
                "expected_modality": sample_import["expected_modality"],
                "expected_languages": values.get("expected_languages", []),
                "expected_tasks": values.get("expected_tasks", []),
                "dataset_version": sample_import["dataset_version"],
                "revision": sample_import["revision"],
                "source_checksum": values.get("source_checksum"),
                "target_fingerprint": fingerprint,
                "requested_by_admin_public_id": admin_id,
            },
        )
        self._samples.record_event(
            sample_import_public_id,
            {
                "event_type": "approval_requested",
                "from_status": sample_import["status"],
                "to_status": "awaiting_approval",
                "summary": "Sample import approval requested",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="request_sample_import_approval",
            actor_reference=admin_id,
            resource_public_id=approval["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return approval

    def is_stale(self, approval_public_id: str) -> bool:
        approval = self._samples.get_approval(approval_public_id)
        sample_import = self._samples.get_sample_import(approval["sample_import_public_id"])
        return self._current_fingerprint(sample_import) != approval["target_fingerprint"]

    def approve(
        self,
        approval_public_id: str,
        *,
        admin_id: str,
        approved_record_limit: int,
        approved_byte_limit: int,
        expires_at: str,
        approval_reason: str | None = None,
        conditions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.is_stale(approval_public_id):
            raise DatasetSampleImportError(
                "the underlying verification case has changed since this approval was "
                "requested -- reject this approval and request a new one"
            )
        approval = self._samples.approve_approval(
            approval_public_id,
            approved_by_admin_id=admin_id,
            approved_record_limit=approved_record_limit,
            approved_byte_limit=approved_byte_limit,
            expires_at=expires_at,
            approval_reason=approval_reason,
            conditions=conditions,
        )
        self._samples.record_event(
            approval["sample_import_public_id"],
            {
                "event_type": "approved",
                "to_status": "approved",
                "summary": f"Sample import approved by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="approve_sample_import",
            actor_reference=admin_id,
            resource_public_id=approval_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "approved_record_limit": approved_record_limit,
                "approved_byte_limit": approved_byte_limit,
            },
        )
        return approval

    def reject(self, approval_public_id: str, *, admin_id: str, reason: str) -> dict[str, Any]:
        approval = self._samples.reject_approval(approval_public_id)
        self._samples.record_event(
            approval["sample_import_public_id"],
            {
                "event_type": "approval_rejected",
                "to_status": "rejected",
                "summary": reason,
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="reject_sample_import_approval",
            actor_reference=admin_id,
            resource_public_id=approval_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"reason": reason},
        )
        return approval

    def get_latest_approval(self, sample_import_public_id: str) -> dict[str, Any] | None:
        return self._samples.get_latest_approval(sample_import_public_id)
