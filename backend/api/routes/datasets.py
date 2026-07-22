"""Authenticated manual dataset-management API."""

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.models.datasets import (
    ManualSourceCreate,
    Page,
    RecordCreate,
    RecordPatch,
    ReviewRequest,
    SourcePatch,
)
from backend.services.dataset_service import DatasetService

router = APIRouter(
    prefix="/admin/datasets", tags=["admin-datasets"], dependencies=[Depends(require_admin)]
)


def service(settings) -> DatasetService:
    return DatasetService(DatasetAdminRepository(settings.resolved_database_path))


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
