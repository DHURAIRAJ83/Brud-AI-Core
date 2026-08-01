"""Phase 3 (Data Studio) Manual Data Studio API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.manual_data import ManualDataRepository
from backend.models.manual_data import (
    ApprovalRequest,
    CreateCandidateRequest,
    ManualDataRecordCreate,
    ManualDataRecordPatch,
    RejectRequest,
    ReviewRequest,
    RevisionCreate,
    UsageCheckRequest,
    VerificationRequest,
)
from backend.services.dataset_service import DatasetService
from backend.services.manual_data_candidate_service import ManualDataCandidateService
from backend.services.manual_data_service import (
    ManualDataQualityService,
    ManualDataRecordService,
    ManualDataReviewService,
    ManualDataUsageService,
    ManualDataVerificationService,
)

router = APIRouter(
    prefix="/admin/manual-data", tags=["admin-manual-data"], dependencies=[Depends(require_admin)]
)


def _manual_repository(settings) -> ManualDataRepository:
    return ManualDataRepository(settings.resolved_database_path)


def _source_repository(settings) -> DataSourceRepository:
    return DataSourceRepository(settings.resolved_database_path)


def record_service(settings) -> ManualDataRecordService:
    return ManualDataRecordService(
        _manual_repository(settings), _source_repository(settings), settings
    )


def review_service(settings) -> ManualDataReviewService:
    return ManualDataReviewService(_manual_repository(settings), settings)


def verification_service(settings) -> ManualDataVerificationService:
    return ManualDataVerificationService(
        _manual_repository(settings), _source_repository(settings), settings
    )


def quality_service(settings) -> ManualDataQualityService:
    return ManualDataQualityService(_manual_repository(settings), settings)


def usage_service(settings) -> ManualDataUsageService:
    return ManualDataUsageService(
        _manual_repository(settings), _source_repository(settings), settings
    )


def candidate_service(settings) -> ManualDataCandidateService:
    dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
    return ManualDataCandidateService(_manual_repository(settings), dataset_service, settings)


# --- records -------------------------------------------------------------


@router.get("")
async def list_records(
    settings: SettingsDependency,
    status: str | None = None,
    record_type: str | None = None,
    creation_method: str | None = None,
    knowledge_risk: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
) -> dict[str, Any]:
    return record_service(settings).list(
        status=status,
        record_type=record_type,
        creation_method=creation_method,
        knowledge_risk=knowledge_risk,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.get("/summary")
async def summary(settings: SettingsDependency) -> dict[str, Any]:
    return record_service(settings).summary()


@router.post("")
async def create_record(
    payload: ManualDataRecordCreate, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return record_service(settings).create(payload, admin_id=admin.admin.public_id)


@router.get("/{record_id}")
async def get_record(record_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return record_service(settings).get(record_id)


@router.patch("/{record_id}")
async def update_record(
    record_id: str,
    payload: ManualDataRecordPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return record_service(settings).update(record_id, payload, admin_id=admin.admin.public_id)


@router.post("/{record_id}/archive")
async def archive_record(
    record_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return record_service(settings).archive(record_id, admin_id=admin.admin.public_id)


@router.post("/{record_id}/restore")
async def restore_record(
    record_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return record_service(settings).restore(record_id, admin_id=admin.admin.public_id)


# --- revisions -------------------------------------------------------------


@router.get("/{record_id}/revisions")
async def list_revisions(record_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return record_service(settings).list_revisions(record_id)


@router.post("/{record_id}/revisions")
async def create_revision(
    record_id: str,
    payload: RevisionCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return record_service(settings).create_revision(
        record_id, payload, admin_id=admin.admin.public_id
    )


@router.get("/{record_id}/revisions/{revision_id}")
async def get_revision(
    record_id: str, revision_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return record_service(settings).get_revision(record_id, revision_id)


# --- lifecycle ---------------------------------------------------------------


@router.post("/{record_id}/submit-review")
async def submit_review(
    record_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return record_service(settings).submit_review(record_id, admin_id=admin.admin.public_id)


@router.post("/{record_id}/request-correction")
async def request_correction(
    record_id: str, settings: SettingsDependency, admin: CsrfDependency, notes: str = ""
) -> dict[str, Any]:
    return record_service(settings).request_correction(
        record_id, admin_id=admin.admin.public_id, notes=notes
    )


@router.post("/{record_id}/request-source-verification")
async def request_source_verification(
    record_id: str, settings: SettingsDependency, admin: CsrfDependency, notes: str = ""
) -> dict[str, Any]:
    return record_service(settings).request_source_verification(
        record_id, admin_id=admin.admin.public_id, notes=notes
    )


@router.post("/{record_id}/request-domain-review")
async def request_domain_review(
    record_id: str, settings: SettingsDependency, admin: CsrfDependency, notes: str = ""
) -> dict[str, Any]:
    return record_service(settings).request_domain_review(
        record_id, admin_id=admin.admin.public_id, notes=notes
    )


@router.post("/{record_id}/review")
async def submit_record_review(
    record_id: str,
    payload: ReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return review_service(settings).submit(record_id, payload, admin_id=admin.admin.public_id)


@router.get("/{record_id}/reviews")
async def list_record_reviews(record_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return review_service(settings).list(record_id)


@router.post("/{record_id}/verify")
async def submit_verification(
    record_id: str,
    payload: VerificationRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return verification_service(settings).submit(record_id, payload, admin_id=admin.admin.public_id)


@router.get("/{record_id}/verifications")
async def list_verifications(record_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return verification_service(settings).list(record_id)


@router.post("/{record_id}/approve")
async def approve_record(
    record_id: str,
    payload: ApprovalRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return record_service(settings).approve(
        record_id, payload, admin_id=admin.admin.public_id, usage_service=usage_service(settings)
    )


@router.post("/{record_id}/reject")
async def reject_record(
    record_id: str,
    payload: RejectRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return record_service(settings).reject(record_id, payload, admin_id=admin.admin.public_id)


# --- quality & duplicates ----------------------------------------------------


@router.post("/{record_id}/quality-check")
async def quality_check(record_id: str, settings: SettingsDependency) -> dict[str, Any]:
    duplicate = quality_service(settings).check_duplicates(record_id)
    return quality_service(settings).assess(
        record_id, duplicate_status=duplicate["duplicate_status"]
    )


@router.post("/{record_id}/duplicate-check")
async def duplicate_check(record_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return quality_service(settings).check_duplicates(record_id)


# --- usage -------------------------------------------------------------------


@router.post("/{record_id}/usage-check")
async def usage_check(
    record_id: str,
    payload: UsageCheckRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return usage_service(settings).evaluate(
        record_id, payload.target_use, admin_id=admin.admin.public_id
    )


@router.get("/{record_id}/usage-summary")
async def usage_summary(record_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return usage_service(settings).summary(record_id)


# --- history & candidate -------------------------------------------------


@router.get("/{record_id}/history")
async def record_history(record_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return record_service(settings).history(record_id)


@router.post("/{record_id}/create-dataset-candidate")
async def create_dataset_candidate(
    record_id: str,
    payload: CreateCandidateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return candidate_service(settings).create_candidate(
        record_id, admin_id=admin.admin.public_id, notes=payload.notes
    )
