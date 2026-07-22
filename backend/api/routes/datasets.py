"""Authenticated manual dataset-management API."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.models.dataset_quality import BulkQualityAssessRequest, QualityAssessRequest
from backend.models.dataset_versions import (
    ArchiveVersionRequest,
    BuildCreate,
    BuildRunRequest,
    DatasetVersionCreate,
    DatasetVersionPatch,
    ExportCreate,
)
from backend.models.datasets import (
    ManualSourceCreate,
    Page,
    RecordCreate,
    RecordPatch,
    ReviewRequest,
    SourcePatch,
)
from backend.services.dataset_quality import DatasetQualityService
from backend.services.dataset_service import DatasetService
from backend.services.dataset_versioning import DatasetVersioningService

router = APIRouter(
    prefix="/admin/datasets", tags=["admin-datasets"], dependencies=[Depends(require_admin)]
)


def service(settings) -> DatasetService:
    return DatasetService(DatasetAdminRepository(settings.resolved_database_path))


def quality_service(settings) -> DatasetQualityService:
    return DatasetQualityService(
        DatasetQualityRepository(settings.resolved_database_path), settings
    )


def version_service(settings) -> DatasetVersioningService:
    return DatasetVersioningService(
        DatasetQualityRepository(settings.resolved_database_path), settings
    )


@router.get("/sources", response_model=Page)
async def list_sources(
    settings: SettingsDependency,
    status: str | None = None,
    language: str | None = None,
    source_type: str | None = None,
    licence_status: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Page:
    return service(settings).list_sources(locals(), page, page_size)


@router.post("/sources")
async def create_source(
    payload: ManualSourceCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).create_source(payload, admin.admin.public_id)


@router.get("/sources/{public_id}")
async def get_source(public_id: str, settings: SettingsDependency):
    return service(settings).get_source(public_id)


@router.patch("/sources/{public_id}")
async def update_source(
    public_id: str,
    payload: SourcePatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).update_source(public_id, payload, admin.admin.public_id)


@router.get("/records", response_model=Page)
async def list_records(
    settings: SettingsDependency,
    status: str | None = None,
    language: str | None = None,
    record_type: str | None = None,
    source: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
) -> Page:
    return service(settings).list_records(locals(), page, page_size)


@router.post("/records")
async def create_record(payload: RecordCreate, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_record(payload, admin.admin.public_id)


@router.get("/records/{public_id}")
async def get_record(public_id: str, settings: SettingsDependency):
    return service(settings).get_record(public_id)


@router.patch("/records/{public_id}")
async def update_record(
    public_id: str,
    payload: RecordPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).update_record(public_id, payload, admin.admin.public_id)


@router.post("/records/{public_id}/submit")
async def submit_record(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).transition(
        public_id, "pending_review", "edit", None, admin.admin.public_id
    )


@router.post("/records/{public_id}/review")
async def review_record(
    public_id: str,
    payload: ReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).review(
        public_id, payload.decision, payload.comments, admin.admin.public_id
    )


@router.post("/records/{public_id}/archive")
async def archive_record(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).transition(public_id, "archived", "edit", None, admin.admin.public_id)


@router.post("/records/{public_id}/restore")
async def restore_record(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).transition(public_id, "draft", "restore", None, admin.admin.public_id)


@router.get("/records/{public_id}/reviews")
async def review_history(public_id: str, settings: SettingsDependency):
    return {"items": service(settings).reviews(public_id)}


@router.get("/statistics")
async def statistics(settings: SettingsDependency):
    return service(settings).statistics()


@router.get("/duplicates")
async def duplicates(settings: SettingsDependency):
    return {"items": service(settings).duplicates()}


@router.post("/records/{public_id}/quality/assess")
async def assess_record_quality(
    public_id: str,
    payload: QualityAssessRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    _ = payload
    return quality_service(settings).assess_record(public_id, admin.admin.public_id)


@router.get("/records/{public_id}/quality")
async def record_quality(public_id: str, settings: SettingsDependency):
    return quality_service(settings).latest(public_id)


@router.get("/records/{public_id}/quality/issues")
async def record_quality_issues(public_id: str, settings: SettingsDependency):
    return quality_service(settings).issues(public_id)


@router.post("/quality/assess")
async def assess_quality_bulk(
    payload: BulkQualityAssessRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return quality_service(settings).assess_filtered(payload, admin.admin.public_id)


@router.get("/quality/summary")
async def quality_summary(settings: SettingsDependency):
    return quality_service(settings).summary()


@router.get("/quality/issues")
async def quality_issues(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return quality_service(settings).all_issues(page, page_size)


@router.get("/versions")
async def list_versions(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return version_service(settings).list_versions(page, page_size)


@router.post("/versions")
async def create_version(
    payload: DatasetVersionCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return version_service(settings).create_version(payload, admin.admin.public_id)


@router.get("/versions/{public_id}")
async def get_version(public_id: str, settings: SettingsDependency):
    return version_service(settings).get_version(public_id)


@router.patch("/versions/{public_id}")
async def patch_version(
    public_id: str,
    payload: DatasetVersionPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return version_service(settings).patch_version(
        public_id, payload.model_dump(exclude_unset=True), admin.admin.public_id
    )


@router.post("/versions/{public_id}/archive")
async def archive_version(
    public_id: str,
    payload: ArchiveVersionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    _ = payload
    return version_service(settings).archive_version(public_id, admin.admin.public_id)


@router.get("/versions/{public_id}/items")
async def version_items(
    public_id: str,
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return version_service(settings).version_items(public_id, page, page_size)


@router.get("/versions/{public_id}/manifest")
async def version_manifest(public_id: str, settings: SettingsDependency):
    return version_service(settings).manifest(public_id)


@router.post("/versions/{public_id}/verify")
async def verify_version(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return version_service(settings).verify_version(public_id, admin.admin.public_id)


@router.post("/builds")
async def create_build(payload: BuildCreate, settings: SettingsDependency, admin: CsrfDependency):
    return version_service(settings).create_build(payload, admin.admin.public_id)


@router.get("/builds")
async def list_builds(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return version_service(settings).list_builds(page, page_size)


@router.get("/builds/{public_id}")
async def get_build(public_id: str, settings: SettingsDependency):
    return version_service(settings).get_build(public_id)


@router.post("/builds/{public_id}/validate")
async def validate_build(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return version_service(settings).validate_build(public_id, admin.admin.public_id)


@router.post("/builds/{public_id}/run")
async def run_build(
    public_id: str,
    payload: BuildRunRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return version_service(settings).run_build(public_id, payload, admin.admin.public_id)


@router.post("/builds/{public_id}/cancel")
async def cancel_build(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    _ = admin
    return version_service(settings).get_build(public_id)


@router.get("/builds/{public_id}/events")
async def build_events(public_id: str, settings: SettingsDependency):
    return version_service(settings).events(public_id)


@router.post("/versions/{public_id}/exports")
async def create_export(
    public_id: str,
    payload: ExportCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return version_service(settings).create_export(
        public_id, payload.export_format, admin.admin.public_id
    )


@router.get("/versions/{public_id}/exports")
async def version_exports(public_id: str, settings: SettingsDependency):
    return version_service(settings).list_exports(public_id)


@router.get("/exports/{export_public_id}")
async def get_export(export_public_id: str, settings: SettingsDependency):
    return version_service(settings).get_export(export_public_id)


@router.get("/exports/{export_public_id}/download")
async def download_export(export_public_id: str, settings: SettingsDependency):
    path = version_service(settings).export_file(export_public_id)
    return Response(
        content=path.read_bytes(),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="manifest.json"'},
    )


@router.post("/exports/{export_public_id}/verify")
async def verify_export(export_public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return version_service(settings).verify_export(export_public_id, admin.admin.public_id)
