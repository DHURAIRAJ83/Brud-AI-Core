"""Phase 13 Step 4 eligibility gate and Step 5 sandbox-experiment
approval binding.

Reads Phase 12's finalized sample-validation report (read-only) and
Phase 11's verification case (read-only) to decide whether a bounded
RAG-sandbox experiment proposal may even be created, then owns the
separate, explicitly bound approval record a human Admin must sign off
on before any record is promoted or any index is built. Never mutates
a Phase 12 sample import or a Phase 11 verification case. See
docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.core.json_utils import dumps_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.models.domain import AuditEventCreate, AuditOutcome

logger = logging.getLogger(__name__)


class RagSandboxError(BrudError):
    status_code = 422
    code = "rag_sandbox_rejected"


def compute_target_fingerprint(
    *,
    sample_report_checksum: str,
    accepted_record_checksum_set_hash: str,
    purpose: str,
    query_set_public_id: str | None,
    maximum_records: int,
    maximum_total_characters: int,
    maximum_total_tokens: int,
) -> str:
    """A stable digest of every fact a bound approval must stay pinned
    to -- if the finalized sample report is superseded, the accepted-
    record set changes, or any bound configuration changes after
    approval, a freshly computed fingerprint stops matching the
    approval's own stored one and the build/download is rejected as
    stale. Deliberately pure (no I/O) so both the approval service and
    the Admin Assistant's ``STALE_CHECK_FINGERPRINTS`` registry can
    call it identically."""

    payload = {
        "sample_report_checksum": sample_report_checksum,
        "accepted_record_checksum_set_hash": accepted_record_checksum_set_hash,
        "purpose": purpose,
        "query_set_public_id": query_set_public_id,
        "maximum_records": maximum_records,
        "maximum_total_characters": maximum_total_characters,
        "maximum_total_tokens": maximum_total_tokens,
    }
    return hashlib.sha256(dumps_json(payload).encode("utf-8")).hexdigest()


def accepted_record_checksum_set_hash(checksums: list[str]) -> str:
    return hashlib.sha256(dumps_json(sorted(checksums)).encode("utf-8")).hexdigest()


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


class RagSandboxEligibilityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._verification = DatasetVerificationRepository(settings.resolved_database_path)
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def check_eligibility(self, sample_import_public_id: str) -> dict[str, Any]:
        """Every check from Step 4, run read-only. Never raises for a
        blocked outcome -- callers decide whether to surface it as an
        error (`create_experiment`) or just display it."""

        checks: dict[str, dict[str, Any]] = {}
        blocking_reasons: list[str] = []
        warnings: list[str] = []

        sample_import = self._samples.get_sample_import(sample_import_public_id)
        finalized = sample_import["locked_at"] is not None
        checks["sample_report_finalized"] = {"passed": finalized}
        if not finalized:
            blocking_reasons.append("Phase 12 sample import is not yet finalized")

        eligible = bool(sample_import["rag_sandbox_eligible"])
        checks["rag_sandbox_eligible"] = {"passed": eligible}
        if not eligible:
            blocking_reasons.append("Phase 12 report marked rag_sandbox_eligible=false")

        report = self._samples.get_latest_report(sample_import_public_id)
        checks["sample_report_exists"] = {"passed": report is not None}
        if report is None:
            blocking_reasons.append("no finalized Phase 12 sample-validation report exists")

        accepted_records = (
            self._samples.list_records(
                sample_import_public_id, status="accepted", limit=100, offset=0
            )
            if finalized
            else []
        )
        has_accepted = len(accepted_records) > 0
        checks["accepted_records_exist"] = {
            "passed": has_accepted, "accepted_record_count": len(accepted_records),
        }
        if not has_accepted:
            blocking_reasons.append("no accepted Phase 12 records exist for this sample import")

        unresolved_pii = (
            self._samples.list_record_issues(
                sample_import_public_id, issue_category="pii", status="blocked"
            )
            if finalized
            else []
        )
        no_unresolved_pii = len(unresolved_pii) == 0
        checks["no_unresolved_blocking_pii"] = {"passed": no_unresolved_pii}
        if not no_unresolved_pii:
            blocking_reasons.append("one or more PII findings remain blocked and unresolved")

        unresolved_security = (
            self._samples.list_scan_results(sample_import_public_id) if finalized else []
        )
        blocked_scans = [row for row in unresolved_security if row["verdict"] == "blocked"]
        no_security_blocker = len(blocked_scans) == 0
        checks["no_unresolved_security_blocker"] = {"passed": no_security_blocker}
        if not no_security_blocker:
            blocking_reasons.append("one or more file-safety scans are blocked")

        case = self._verification.get_case(sample_import["verification_case_public_id"])
        withdrawal_notices = self._verification.list_withdrawal_notices(
            sample_import["verification_case_public_id"]
        )
        no_rights_withdrawal = len(withdrawal_notices) == 0
        checks["no_rights_withdrawal"] = {"passed": no_rights_withdrawal}
        if not no_rights_withdrawal:
            blocking_reasons.append(
                "an active provider/rights withdrawal notice blocks new imports"
            )

        verification_current = case["verification_expiry_status"] not in (
            "expired", "source_changed", "withdrawn",
        )
        checks["phase11_verification_current"] = {
            "passed": verification_current,
            "verification_expiry_status": case["verification_expiry_status"],
        }
        if not verification_current:
            blocking_reasons.append("Phase 11 verification is no longer current")

        rag_permission = self._verification.get_permission_assessment(
            sample_import["verification_case_public_id"], "rag_use"
        )
        rag_permission_status = rag_permission["status"] if rag_permission else "not_assessed"
        rag_permission_ok = rag_permission_status not in ("not_approved", "prohibited")
        checks["rag_use_permission_not_denied"] = {
            "passed": rag_permission_ok, "status": rag_permission_status,
        }
        if not rag_permission_ok:
            blocking_reasons.append(f"'rag_use' permission is '{rag_permission_status}'")

        commercial = self._verification.get_permission_assessment(
            sample_import["verification_case_public_id"], "commercial_use"
        )
        checks["commercial_permission_displayed"] = {
            "passed": True, "status": commercial["status"] if commercial else "not_assessed",
        }
        if not commercial:
            warnings.append("commercial-use permission has not yet been assessed for this dataset")

        checks["provider_and_source_lineage_intact"] = {
            "passed": bool(sample_import.get("candidate_public_id"))
            and bool(sample_import.get("verification_case_public_id")),
        }

        checksums = sorted(row["record_checksum"] for row in accepted_records)
        checksum_set_hash = accepted_record_checksum_set_hash(checksums)

        return {
            "eligible": len(blocking_reasons) == 0,
            "checks": checks,
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
            "sample_import": sample_import,
            "sample_report": report,
            "verification_case_public_id": sample_import["verification_case_public_id"],
            "accepted_records": accepted_records,
            "accepted_record_checksum_set_hash": checksum_set_hash,
        }

    def create_experiment(
        self, sample_import_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        """The one entry point that turns an eligibility pass into a
        real `draft` sandbox-experiment row -- refuses outright if the
        gate is not clear. Never promotes a record, never builds an
        index, and never activates production RAG; this only opens the
        experiment for a bounded, still-unapproved proposal (Step 4)."""

        result = self.check_eligibility(sample_import_public_id)
        if not result["eligible"]:
            raise RagSandboxError(
                "rag sandbox experiment is not eligible: " + "; ".join(result["blocking_reasons"])
            )
        purpose = values["purpose"]
        admin_id = values["created_by_admin_public_id"]
        experiment = self._sandbox.create_experiment(
            {
                "experiment_code": values.get("experiment_code") or f"RSE-{uuid4().hex[:16]}",
                "sample_import_public_id": sample_import_public_id,
                "sample_report_public_id": result["sample_report"]["public_id"],
                "verification_case_public_id": result["verification_case_public_id"],
                "purpose": purpose,
                "sample_report_checksum": hashlib.sha256(
                    dumps_json(result["sample_report"]["report"]).encode("utf-8")
                ).hexdigest(),
                "accepted_record_checksum_set_hash": result["accepted_record_checksum_set_hash"],
                "maximum_records": values.get("maximum_records", 500),
                "maximum_total_characters": values.get("maximum_total_characters", 2_000_000),
                "maximum_total_tokens": values.get("maximum_total_tokens", 500_000),
                "expires_at": values.get("expires_at"),
                "created_by_admin_public_id": admin_id,
            }
        )
        self._sandbox.record_event(
            experiment["public_id"],
            {
                "event_type": "experiment_created",
                "to_status": "draft",
                "summary": f"RAG sandbox experiment proposal created for purpose '{purpose}'",
                "metadata": {"warnings": result["warnings"]},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="create_experiment",
            actor_reference=admin_id,
            resource_public_id=experiment["public_id"],
            outcome=AuditOutcome.SUCCESS,
            metadata={"purpose": purpose, "warnings": result["warnings"]},
        )
        return experiment


class RagSandboxApprovalService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._eligibility = RagSandboxEligibilityService(settings)
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _current_fingerprint(
        self, experiment: dict[str, Any], *, purpose: str, query_set_public_id: str | None,
        maximum_records: int, maximum_total_characters: int, maximum_total_tokens: int,
    ) -> str:
        eligibility = self._eligibility.check_eligibility(experiment["sample_import_public_id"])
        sample_report_checksum = hashlib.sha256(
            dumps_json(eligibility["sample_report"]["report"]).encode("utf-8")
        ).hexdigest()
        return compute_target_fingerprint(
            sample_report_checksum=sample_report_checksum,
            accepted_record_checksum_set_hash=eligibility["accepted_record_checksum_set_hash"],
            purpose=purpose,
            query_set_public_id=query_set_public_id,
            maximum_records=maximum_records,
            maximum_total_characters=maximum_total_characters,
            maximum_total_tokens=maximum_total_tokens,
        )

    def request_approval(
        self, experiment_public_id: str, values: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        experiment = self._sandbox.get_experiment(experiment_public_id)
        eligibility = self._eligibility.check_eligibility(experiment["sample_import_public_id"])
        if not eligibility["eligible"]:
            raise RagSandboxError(
                "cannot request approval: " + "; ".join(eligibility["blocking_reasons"])
            )
        accepted_ids = [row["public_id"] for row in eligibility["accepted_records"]]
        accepted_checksums = [row["record_checksum"] for row in eligibility["accepted_records"]]
        purpose = values.get("purpose", experiment["purpose"])
        query_set_public_id = values.get("query_set_public_id")
        maximum_records = values.get("maximum_records", experiment["maximum_records"])
        maximum_total_characters = values.get(
            "maximum_total_characters", experiment["maximum_total_characters"]
        )
        maximum_total_tokens = values.get(
            "maximum_total_tokens", experiment["maximum_total_tokens"]
        )
        fingerprint = self._current_fingerprint(
            experiment,
            purpose=purpose,
            query_set_public_id=query_set_public_id,
            maximum_records=maximum_records,
            maximum_total_characters=maximum_total_characters,
            maximum_total_tokens=maximum_total_tokens,
        )
        approval = self._sandbox.create_approval(
            experiment_public_id,
            {
                "sample_import_public_id": experiment["sample_import_public_id"],
                "sample_report_public_id": experiment["sample_report_public_id"],
                "verification_case_public_id": experiment["verification_case_public_id"],
                "expires_at": values.get("expires_at"),
                "purpose": purpose,
                "accepted_record_ids": accepted_ids,
                "accepted_record_checksums": accepted_checksums,
                "maximum_records": maximum_records,
                "maximum_total_characters": maximum_total_characters,
                "maximum_total_tokens": maximum_total_tokens,
                "chunking_configuration": values.get("chunking_configuration", {}),
                "retrieval_configuration": values.get("retrieval_configuration", {}),
                "embedding_assignment_key": values.get("embedding_assignment_key"),
                "generation_assignment_key": values.get("generation_assignment_key"),
                "query_set_public_id": query_set_public_id,
                "target_fingerprint": fingerprint,
                "conditions": values.get("conditions", {}),
                "requested_by_admin_public_id": admin_id,
            },
        )
        self._sandbox.update_experiment(experiment_public_id, {"status": "awaiting_approval"})
        self._sandbox.record_event(
            experiment_public_id,
            {
                "event_type": "approval_requested",
                "from_status": experiment["status"],
                "to_status": "awaiting_approval",
                "summary": "RAG sandbox approval requested",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="request_approval",
            actor_reference=admin_id,
            resource_public_id=approval["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return approval

    def is_stale(self, approval_public_id: str) -> bool:
        approval = self._sandbox.get_approval(approval_public_id)
        experiment = self._sandbox.get_experiment(approval["experiment_public_id"])
        current = self._current_fingerprint(
            experiment,
            purpose=approval["purpose"],
            query_set_public_id=approval["query_set_public_id"],
            maximum_records=approval["maximum_records"],
            maximum_total_characters=approval["maximum_total_characters"],
            maximum_total_tokens=approval["maximum_total_tokens"],
        )
        return current != approval["target_fingerprint"]

    def approve(
        self, approval_public_id: str, *, admin_id: str, expires_at: str | None = None
    ) -> dict[str, Any]:
        if self.is_stale(approval_public_id):
            raise RagSandboxError(
                "the underlying Phase 12 sample report or accepted-record set has changed "
                "since this approval was requested -- reject this approval and request a new one"
            )
        approval = self._sandbox.approve_approval(
            approval_public_id, approved_by_admin_id=admin_id, expires_at=expires_at
        )
        self._sandbox.update_experiment(approval["experiment_public_id"], {"status": "approved"})
        self._sandbox.record_event(
            approval["experiment_public_id"],
            {
                "event_type": "approved",
                "to_status": "approved",
                "summary": f"RAG sandbox experiment approved by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="approve",
            actor_reference=admin_id,
            resource_public_id=approval_public_id,
            outcome=AuditOutcome.SUCCESS,
        )
        return approval

    def reject(self, approval_public_id: str, *, admin_id: str, reason: str) -> dict[str, Any]:
        approval = self._sandbox.reject_approval(approval_public_id)
        self._sandbox.update_experiment(approval["experiment_public_id"], {"status": "rejected"})
        self._sandbox.record_event(
            approval["experiment_public_id"],
            {
                "event_type": "approval_rejected",
                "to_status": "rejected",
                "summary": reason,
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="reject_approval",
            actor_reference=admin_id,
            resource_public_id=approval_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"reason": reason},
        )
        return approval

    def get_latest_approval(self, experiment_public_id: str) -> dict[str, Any] | None:
        return self._sandbox.get_latest_approval(experiment_public_id)


__all__ = [
    "RagSandboxError",
    "RagSandboxEligibilityService",
    "RagSandboxApprovalService",
    "compute_target_fingerprint",
    "accepted_record_checksum_set_hash",
]
