"""Phase 12 Step 23/24/25: the immutable sample-validation report,
RAG-sandbox eligibility, and the advisory training-assessment signal.

Finalizing is refused outright while any `blocked` scan result or
`blocked` record issue remains unreviewed -- mirrors Phase 11's own
"a blocking conflict prevents finalization until resolved" precedent.
Once those are cleared, `rag_sandbox_eligible` is recomputed from a
fresh Step 6 eligibility check (never cached from approval time) plus
whether any accepted record exists; it is a plain boolean and this
method never creates a RAG index or writes to any RAG table.
`training_assessment_status` is one of the 5 advisory values in
`core_model.sample_import.TRAINING_ASSESSMENT_STATUSES` -- there is no
"approved" value anywhere in that enum, so this method is structurally
incapable of writing one.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.dataset_sample_eligibility_service import (
    ExternalDatasetSampleEligibilityService,
)
from core_model.sample_import import DEFAULT_MAX_SAMPLE_RECORDS

logger = logging.getLogger(__name__)


class DatasetSampleReportError(BrudError):
    status_code = 422
    code = "dataset_sample_report_rejected"


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
        logger.exception("dataset_sample_report_audit_write_failed", extra={"action": action})


class ExternalDatasetSampleReportService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._eligibility = ExternalDatasetSampleEligibilityService(settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _all_records(
        self, sample_import_public_id: str, *, page_size: int = 100
    ) -> list[dict[str, Any]]:
        """Pages through every record for a report (`.list_records()`
        itself is bounded to 100 per call for normal API use) -- capped
        at `DEFAULT_MAX_SAMPLE_RECORDS` pages, matching the approval-
        bound record ceiling this phase never exceeds anyway."""

        records: list[dict[str, Any]] = []
        offset = 0
        while len(records) < DEFAULT_MAX_SAMPLE_RECORDS:
            page = self._samples.list_records(
                sample_import_public_id, limit=page_size, offset=offset
            )
            if not page:
                break
            records.extend(page)
            offset += page_size
        return records

    def finalize(self, sample_import_public_id: str, *, admin_id: str) -> dict[str, Any]:
        sample_import = self._samples.get_sample_import(sample_import_public_id)
        if sample_import["locked_at"] is not None:
            raise DatasetSampleReportError("this sample import has already been finalized")

        files = self._samples.list_files(sample_import_public_id)
        records = self._all_records(sample_import_public_id)
        issues = self._samples.list_record_issues(sample_import_public_id)
        scan_results = self._samples.list_scan_results(sample_import_public_id)
        reviews = self._samples.list_reviews(sample_import_public_id)
        download_events = self._samples.list_download_events(sample_import_public_id)

        reviewed_ok_file_ids = {
            review["target_id"]
            for review in reviews
            if review["target_type"] == "file"
            and review["decision"] in ("accept", "accept_with_conditions")
        }
        unresolved_blocked_scans = [
            scan
            for scan in scan_results
            if scan["verdict"] == "blocked" and scan["file_public_id"] not in reviewed_ok_file_ids
        ]
        unresolved_blocked_issues = [
            issue
            for issue in issues
            if issue["status"] == "blocked" and issue["reviewer_decision"] is None
        ]
        blocking_reasons: list[str] = []
        if unresolved_blocked_scans:
            blocking_reasons.append(
                f"{len(unresolved_blocked_scans)} blocked file(s) have not been reviewed"
            )
        if unresolved_blocked_issues:
            blocking_reasons.append(
                f"{len(unresolved_blocked_issues)} blocked issue(s) have not been reviewed"
            )
        if blocking_reasons:
            raise DatasetSampleReportError(
                "cannot finalize while blocking issues remain unreviewed: "
                + "; ".join(blocking_reasons)
            )

        eligibility = self._eligibility.check_eligibility(
            sample_import["verification_case_public_id"],
            purpose=sample_import["purpose"],
            provider_public_id=sample_import.get("provider_public_id"),
            dataset_version=sample_import["dataset_version"],
            revision=sample_import["revision"],
        )
        accepted_records = [record for record in records if record["status"] == "accepted"]
        excluded_records = [
            record for record in records if record["status"] in ("excluded", "rejected")
        ]
        pii_unresolved = [
            issue
            for issue in issues
            if issue["issue_category"] == "pii"
            and issue["status"] in ("possible", "likely", "confirmed", "blocked")
            and issue["reviewer_decision"] is None
        ]
        contamination_confirmed = [
            issue
            for issue in issues
            if issue["issue_category"] == "contamination" and issue["status"] == "confirmed_overlap"
        ]
        any_unresolved_ambiguous_issue = any(
            issue["status"] in ("possible", "likely") and issue["reviewer_decision"] is None
            for issue in issues
        )

        rag_sandbox_eligible = (
            eligibility["eligible"]
            and not pii_unresolved
            and bool(accepted_records)
            and sample_import["status"] != "withdrawn"
        )
        if contamination_confirmed:
            training_assessment_status = "blocked"
        elif any_unresolved_ambiguous_issue:
            training_assessment_status = "needs_more_review"
        elif accepted_records:
            training_assessment_status = "potentially_suitable"
        else:
            training_assessment_status = "not_suitable"

        report = {
            "source_and_verification_case": {
                "verification_case_public_id": sample_import["verification_case_public_id"],
                "candidate_public_id": sample_import["candidate_public_id"],
            },
            "approval_scope": {
                "purpose": sample_import["purpose"],
                "dataset_version": sample_import["dataset_version"],
                "revision": sample_import["revision"],
            },
            "download_summary": {
                "total_events": len(download_events),
                "completed": sum(1 for e in download_events if e["event_type"] == "completed"),
                "failed": sum(1 for e in download_events if e["event_type"] == "failed"),
            },
            "file_manifest": [
                {"public_id": f["public_id"], "filename": f["safe_filename"], "status": f["status"]}
                for f in files
            ],
            "checksums": {f["safe_filename"]: f["checksum"] for f in files if f["checksum"]},
            "security_findings": [
                {"file_public_id": s["file_public_id"], "verdict": s["verdict"]}
                for s in scan_results
            ],
            "record_counts": {
                "total": len(records),
                "accepted": len(accepted_records),
                "excluded": len(excluded_records),
            },
            "pii_findings": [i for i in issues if i["issue_category"] == "pii"],
            "sensitive_data_findings": [i for i in issues if i["issue_category"] == "pii"],
            "safety_findings": [i for i in issues if i["issue_category"] == "safety"],
            "quality_findings": [i for i in issues if i["issue_category"] == "quality"],
            "duplicate_findings": [i for i in issues if i["issue_category"] == "duplicate"],
            "conflict_findings": [i for i in issues if i["issue_category"] == "conflict"],
            "contamination_findings": [i for i in issues if i["issue_category"] == "contamination"],
            "poisoning_anomaly_findings": [i for i in issues if i["issue_category"] == "poisoning"],
            "human_review_summary": {
                "total_reviews": len(reviews),
                "decisions": {
                    decision: sum(1 for r in reviews if r["decision"] == decision)
                    for decision in {r["decision"] for r in reviews}
                },
            },
            "excluded_records": [r["public_id"] for r in excluded_records],
            "accepted_records": [r["public_id"] for r in accepted_records],
            "conditions": [],
            "blocking_reasons": [],
            "eligibility_blocking_reasons": eligibility["blocking_reasons"],
            "eligibility_warnings": eligibility["warnings"],
            "rag_sandbox_eligible": rag_sandbox_eligible,
            "training_assessment_status": training_assessment_status,
            "recommended_next_step": (
                "Open in the RAG Sandbox (Phase 13)"
                if rag_sandbox_eligible
                else "Resolve eligibility blockers and re-finalize"
            ),
        }

        self._samples.add_report(
            sample_import_public_id,
            {
                "rag_sandbox_eligible": rag_sandbox_eligible,
                "training_assessment_status": training_assessment_status,
                "report": report,
                "finalized_by_admin_public_id": admin_id,
            },
        )
        locked = self._samples.lock_sample_import(
            sample_import_public_id,
            report=report,
            rag_sandbox_eligible=rag_sandbox_eligible,
            training_assessment_status=training_assessment_status,
            status="validated" if rag_sandbox_eligible else "validated_with_conditions",
        )
        self._samples.record_event(
            sample_import_public_id,
            {
                "event_type": "finalized",
                "to_status": "validated" if rag_sandbox_eligible else "validated_with_conditions",
                "summary": f"Report finalized by {admin_id}",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="finalize_sample_validation_report",
            actor_reference=admin_id,
            resource_public_id=sample_import_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "rag_sandbox_eligible": rag_sandbox_eligible,
                "training_assessment_status": training_assessment_status,
            },
        )
        return locked

    def get_latest_report(self, sample_import_public_id: str) -> dict[str, Any] | None:
        return self._samples.get_latest_report(sample_import_public_id)
