"""Phase 12 Approved Sample Import, Quarantine, File Safety, PII &
Data Quality Validation API.

Admin-only, CSRF-protected, under `/api/admin/dataset-sample-imports`.
No endpoint here ever downloads a full external dataset, clones a
repository, executes downloaded content, extracts an unbounded
archive, activates RAG, creates a training dataset version, starts
training, or releases a model. Quarantined file content is never
served as a raw byte stream or public URL -- only bounded metadata and
a safe text preview for supported text files. See
docs/sample_import/phase12_sample_import_quarantine_plan.md.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.services.dataset_sample_deletion_service import ExternalDatasetSampleDeletionService
from backend.services.dataset_sample_download_service import ExternalDatasetSampleDownloadService
from backend.services.dataset_sample_eligibility_service import (
    ExternalDatasetSampleApprovalService,
    ExternalDatasetSampleEligibilityService,
)
from backend.services.dataset_sample_pipeline_service import ExternalDatasetSamplePipelineService
from backend.services.dataset_sample_quarantine_service import (
    ExternalDatasetQuarantineService,
    QuarantineStorageError,
)
from backend.services.dataset_sample_report_service import ExternalDatasetSampleReportService
from backend.services.dataset_sample_review_service import ExternalDatasetSampleReviewService

router = APIRouter(
    prefix="/admin/dataset-sample-imports",
    tags=["dataset-sample-imports"],
    dependencies=[Depends(require_admin)],
)


def repository(settings: SettingsDependency) -> DatasetSampleImportRepository:
    return DatasetSampleImportRepository(settings.resolved_database_path)


def eligibility_service(settings: SettingsDependency) -> ExternalDatasetSampleEligibilityService:
    return ExternalDatasetSampleEligibilityService(settings)


def approval_service(settings: SettingsDependency) -> ExternalDatasetSampleApprovalService:
    return ExternalDatasetSampleApprovalService(settings)


def download_service(settings: SettingsDependency) -> ExternalDatasetSampleDownloadService:
    return ExternalDatasetSampleDownloadService(settings)


def quarantine_service(settings: SettingsDependency) -> ExternalDatasetQuarantineService:
    return ExternalDatasetQuarantineService(settings)


def review_service(settings: SettingsDependency) -> ExternalDatasetSampleReviewService:
    return ExternalDatasetSampleReviewService(settings)


def report_service(settings: SettingsDependency) -> ExternalDatasetSampleReportService:
    return ExternalDatasetSampleReportService(settings)


def deletion_service(settings: SettingsDependency) -> ExternalDatasetSampleDeletionService:
    return ExternalDatasetSampleDeletionService(settings)


def pipeline_service(settings: SettingsDependency) -> ExternalDatasetSamplePipelineService:
    return ExternalDatasetSamplePipelineService(settings)


# -- request models -------------------------------------------------------------------


class SampleImportCreateRequest(DomainModel):
    verification_case_public_id: str
    candidate_public_id: str
    provider_public_id: str | None = None
    purpose: str
    dataset_version: str | None = None
    revision: str | None = None
    selection_method: str
    selection_seed: str | None = None
    source_split: str | None = None
    source_file: str | None = None
    row_start: int | None = None
    row_end: int | None = None
    requested_count: int = Field(default=0, ge=0)
    expected_modality: str = "text"


class ApprovalRequestRequest(DomainModel):
    purpose: str
    requested_record_limit: int = Field(gt=0)
    requested_byte_limit: int = Field(gt=0)
    allowed_file_ids: list[str] = Field(default_factory=list)
    allowed_file_patterns: list[str] = Field(default_factory=list)
    allowed_formats: list[str] = Field(default_factory=list)
    expected_languages: list[str] = Field(default_factory=list)
    expected_tasks: list[str] = Field(default_factory=list)
    source_checksum: str | None = None


class ApprovalDecisionRequest(DomainModel):
    approved_record_limit: int = Field(gt=0)
    approved_byte_limit: int = Field(gt=0)
    expires_at: str
    approval_reason: str | None = Field(default=None, max_length=2000)
    conditions: dict[str, Any] = Field(default_factory=dict)


class ApprovalRejectRequest(DomainModel):
    reason: str = Field(min_length=1, max_length=2000)


class DownloadFileRequest(DomainModel):
    source_url: str = Field(max_length=2000)
    allowed_domains: list[str] = Field(min_length=1)
    original_filename: str | None = None


class RecordReviewRequest(DomainModel):
    decision: str
    reason: str = Field(min_length=1, max_length=2000)
    derived_content_text: str | None = Field(default=None, max_length=200_000)
    conditions: dict[str, Any] = Field(default_factory=dict)


class IssueReviewRequest(DomainModel):
    decision: str
    reason: str = Field(min_length=1, max_length=2000)


class DeletionRequestRequest(DomainModel):
    reason: str = Field(min_length=1, max_length=2000)


# -- overview + sample imports --------------------------------------------------------


@router.get("/overview")
async def get_overview(settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).overview_counts()


@router.post("/sample-imports")
async def create_sample_import(
    payload: SampleImportCreateRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    values = payload.model_dump()
    values["requested_by_admin_public_id"] = admin.admin.public_id
    return eligibility_service(settings).create_sample_import(
        payload.verification_case_public_id, values
    )


@router.get("/sample-imports")
async def list_sample_imports(
    settings: SettingsDependency,
    status: str | None = None,
    verification_case_public_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repository(settings).list_sample_imports(
        status=status,
        verification_case_public_id=verification_case_public_id,
        limit=page_size,
        offset=offset,
    )
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/sample-imports/{sample_import_id}")
async def get_sample_import(sample_import_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_sample_import(sample_import_id)


# -- approval ---------------------------------------------------------------------------


@router.post("/sample-imports/{sample_import_id}/request-approval")
async def request_approval(
    sample_import_id: str,
    payload: ApprovalRequestRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return approval_service(settings).request_approval(
        sample_import_id, payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.post("/sample-imports/{sample_import_id}/approve")
async def approve_sample_import(
    sample_import_id: str,
    payload: ApprovalDecisionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    approval = repository(settings).get_latest_approval(sample_import_id)
    return approval_service(settings).approve(
        approval["public_id"],
        admin_id=admin.admin.public_id,
        approved_record_limit=payload.approved_record_limit,
        approved_byte_limit=payload.approved_byte_limit,
        expires_at=payload.expires_at,
        approval_reason=payload.approval_reason,
        conditions=payload.conditions,
    )


@router.post("/sample-imports/{sample_import_id}/reject-approval")
async def reject_approval(
    sample_import_id: str,
    payload: ApprovalRejectRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    approval = repository(settings).get_latest_approval(sample_import_id)
    return approval_service(settings).reject(
        approval["public_id"], admin_id=admin.admin.public_id, reason=payload.reason
    )


@router.post("/sample-imports/{sample_import_id}/cancel")
async def cancel_sample_import(
    sample_import_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return repository(settings).update_sample_import(
        sample_import_id, {"status": "cancelled", "cancelled_at": _now()}
    )


# -- download + files ---------------------------------------------------------------------


@router.post("/sample-imports/{sample_import_id}/download")
async def download_file(
    sample_import_id: str,
    payload: DownloadFileRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return download_service(settings).download_file(
        sample_import_id,
        source_url=payload.source_url,
        allowed_domains=set(payload.allowed_domains),
        admin_id=admin.admin.public_id,
        original_filename=payload.original_filename,
    )


@router.get("/sample-imports/{sample_import_id}/files")
async def list_files(sample_import_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_files(sample_import_id)}


@router.get("/sample-imports/{sample_import_id}/files/{file_id}")
async def get_file(
    sample_import_id: str,
    file_id: str,
    settings: SettingsDependency,
    preview: bool = False,
) -> dict[str, Any]:
    files = repository(settings).list_files(sample_import_id)
    file_record = next((f for f in files if f["public_id"] == file_id), None)
    if file_record is None:
        from backend.database.repositories.base import NotFoundError

        raise NotFoundError("sample file not found")
    result: dict[str, Any] = dict(file_record)
    result.pop("relative_path", None)  # never expose an internal filesystem path
    if preview and file_record["status"] == "safe_for_scan" and not file_record["is_archive"]:
        try:
            result["text_preview"] = quarantine_service(settings).get_safe_text_preview(
                sample_import_id, file_record["safe_filename"]
            )
        except QuarantineStorageError:
            result["text_preview"] = None
    return result


# -- validation / extraction / scanning / parsing --------------------------------------


@router.post("/sample-imports/{sample_import_id}/validate-files")
async def validate_files(
    sample_import_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    items = pipeline_service(settings).validate_files(
        sample_import_id, admin_id=admin.admin.public_id
    )
    return {"items": items}


@router.post("/sample-imports/{sample_import_id}/extract")
async def extract_archives(
    sample_import_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    items = pipeline_service(settings).extract_archives(
        sample_import_id, admin_id=admin.admin.public_id
    )
    return {"items": items}


@router.post("/sample-imports/{sample_import_id}/scan")
async def scan_files(
    sample_import_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    items = pipeline_service(settings).scan_files(sample_import_id, admin_id=admin.admin.public_id)
    return {"items": items}


@router.post("/sample-imports/{sample_import_id}/parse")
async def parse_files(
    sample_import_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    items = pipeline_service(settings).parse_files(sample_import_id, admin_id=admin.admin.public_id)
    return {"items": items}


# -- records + issues ---------------------------------------------------------------------


@router.get("/sample-imports/{sample_import_id}/records")
async def list_records(
    sample_import_id: str,
    settings: SettingsDependency,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repository(settings).list_records(
        sample_import_id, status=status, limit=page_size, offset=offset
    )
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/sample-imports/{sample_import_id}/records/{record_id}")
async def get_record(
    sample_import_id: str, record_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return repository(settings).get_record(record_id)


@router.post("/sample-imports/{sample_import_id}/records/{record_id}/review")
async def review_record(
    sample_import_id: str,
    record_id: str,
    payload: RecordReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    review = review_service(settings).review_target(
        sample_import_id,
        target_type="record",
        target_id=record_id,
        decision=payload.decision,
        reason=payload.reason,
        reviewer_admin_public_id=admin.admin.public_id,
        derived_content_text=payload.derived_content_text,
        conditions=payload.conditions,
    )
    if payload.decision in ("accept", "accept_with_conditions"):
        repository(settings).update_record_status(record_id, "accepted")
    elif payload.decision in ("exclude", "reject_file", "reject_sample"):
        repository(settings).update_record_status(record_id, "excluded")
    return review


@router.post("/sample-imports/{sample_import_id}/records/{record_id}/create-revision")
async def create_record_revision(
    sample_import_id: str,
    record_id: str,
    payload: RecordReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).review_target(
        sample_import_id,
        target_type="record",
        target_id=record_id,
        decision="edit_derived_copy",
        reason=payload.reason,
        reviewer_admin_public_id=admin.admin.public_id,
        derived_content_text=payload.derived_content_text,
        conditions=payload.conditions,
    )


@router.get("/sample-imports/{sample_import_id}/issues")
async def list_issues(
    sample_import_id: str,
    settings: SettingsDependency,
    issue_category: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    items = repository(settings).list_record_issues(
        sample_import_id, issue_category=issue_category, status=status
    )
    return {"items": items}


@router.post("/sample-imports/{sample_import_id}/issues/{issue_id}/review")
async def review_issue(
    sample_import_id: str,
    issue_id: str,
    payload: IssueReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).review_target(
        sample_import_id,
        target_type="issue",
        target_id=issue_id,
        decision=payload.decision,
        reason=payload.reason,
        reviewer_admin_public_id=admin.admin.public_id,
    )


# -- quality / duplicate / contamination checks ---------------------------------------------


@router.post("/sample-imports/{sample_import_id}/run-quality-checks")
async def run_quality_checks(
    sample_import_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    items = pipeline_service(settings).run_quality_checks(
        sample_import_id, admin_id=admin.admin.public_id
    )
    return {"items": items}


@router.post("/sample-imports/{sample_import_id}/run-duplicate-checks")
async def run_duplicate_checks(
    sample_import_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    items = pipeline_service(settings).run_duplicate_checks(
        sample_import_id, admin_id=admin.admin.public_id
    )
    return {"items": items}


@router.post("/sample-imports/{sample_import_id}/run-contamination-checks")
async def run_contamination_checks(
    sample_import_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    items = pipeline_service(settings).run_contamination_checks(
        sample_import_id, admin_id=admin.admin.public_id
    )
    return {"items": items}


# -- finalize + report -------------------------------------------------------------------


@router.post("/sample-imports/{sample_import_id}/finalize")
async def finalize_sample_import(
    sample_import_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return report_service(settings).finalize(sample_import_id, admin_id=admin.admin.public_id)


@router.get("/sample-imports/{sample_import_id}/report")
async def get_report(sample_import_id: str, settings: SettingsDependency) -> dict[str, Any]:
    report = report_service(settings).get_latest_report(sample_import_id)
    from backend.database.repositories.base import NotFoundError

    if report is None:
        raise NotFoundError("no finalized report exists for this sample import")
    return report


# -- deletion ---------------------------------------------------------------------------


@router.post("/sample-imports/{sample_import_id}/request-deletion")
async def request_deletion(
    sample_import_id: str,
    payload: DeletionRequestRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return deletion_service(settings).request_deletion(
        sample_import_id, admin_id=admin.admin.public_id, reason=payload.reason
    )


@router.post("/sample-imports/{sample_import_id}/execute-deletion")
async def execute_deletion(
    sample_import_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    service = deletion_service(settings)
    latest = repository(settings).get_latest_deletion_request(sample_import_id)
    if latest is None:
        from backend.database.repositories.base import NotFoundError

        raise NotFoundError("no deletion request exists for this sample import")
    service.confirm_deletion(latest["deletion_request_code"], admin_id=admin.admin.public_id)
    return service.execute_deletion(
        latest["deletion_request_code"], admin_id=admin.admin.public_id
    )


@router.get("/sample-imports/{sample_import_id}/events")
async def list_events(
    sample_import_id: str,
    settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=200),
) -> dict[str, Any]:
    return {"items": repository(settings).list_events(sample_import_id, limit=limit)}


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
