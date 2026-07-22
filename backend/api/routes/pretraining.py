"""Authenticated bounded core-model pretraining APIs."""

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.pretraining import PretrainingRepository
from backend.models.pretraining import (
    CheckpointCompareRequest,
    PretrainingJobCreate,
    PretrainingJobPatch,
)
from backend.services.pretraining_service import PretrainingService

router = APIRouter(
    prefix="/admin/pretraining",
    tags=["admin-pretraining"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> PretrainingService:
    return PretrainingService(PretrainingRepository(settings.resolved_database_path), settings)


@router.get("/capabilities")
async def capabilities(settings: SettingsDependency):
    return service(settings).capabilities()


@router.post("/estimate")
async def estimate(
    payload: PretrainingJobCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).estimate(payload)


@router.post("/preflight")
async def preflight(
    payload: PretrainingJobCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).preflight_payload(payload)


@router.get("/jobs")
async def jobs(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).list_jobs(page, page_size)


@router.post("/jobs")
async def create_job(
    payload: PretrainingJobCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).create_job(payload, admin.admin.public_id)


@router.get("/jobs/{public_id}")
async def job(public_id: str, settings: SettingsDependency):
    return service(settings).get_job(public_id)


@router.patch("/jobs/{public_id}")
async def patch_job(
    public_id: str,
    payload: PretrainingJobPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_job(public_id, payload, admin.admin.public_id)


@router.post("/jobs/{public_id}/validate")
async def validate_job(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).validate_job(public_id, admin.admin.public_id)


@router.post("/jobs/{public_id}/queue")
async def queue_job(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).queue_job(public_id, admin.admin.public_id)


@router.post("/jobs/{public_id}/pause")
async def pause_job(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).pause(public_id, admin.admin.public_id)


@router.post("/jobs/{public_id}/resume")
async def resume_job(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).resume(public_id, admin.admin.public_id)


@router.post("/jobs/{public_id}/cancel")
async def cancel_job(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).cancel(public_id, admin.admin.public_id)


@router.get("/jobs/{public_id}/events")
async def job_events(public_id: str, settings: SettingsDependency):
    return service(settings).events(public_id)


@router.get("/jobs/{public_id}/metrics")
async def job_metrics(public_id: str, settings: SettingsDependency):
    return service(settings).metrics(public_id)


@router.get("/jobs/{public_id}/checkpoints")
async def job_checkpoints(public_id: str, settings: SettingsDependency):
    return service(settings).checkpoints(public_id)


@router.get("/pretraining/checkpoints/{checkpoint_public_id}", include_in_schema=False)
async def legacy_checkpoint(checkpoint_public_id: str, settings: SettingsDependency):
    return service(settings).checkpoint(checkpoint_public_id)


@router.get("/checkpoints/{checkpoint_public_id}")
async def checkpoint(checkpoint_public_id: str, settings: SettingsDependency):
    return service(settings).checkpoint(checkpoint_public_id)


@router.post("/checkpoints/{checkpoint_public_id}/verify")
async def verify_checkpoint(
    checkpoint_public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).verify_checkpoint(checkpoint_public_id, admin.admin.public_id)


@router.post("/checkpoints/compare")
async def compare_checkpoints(payload: CheckpointCompareRequest, settings: SettingsDependency):
    return service(settings).compare_checkpoints(
        payload.left_checkpoint_public_id,
        payload.right_checkpoint_public_id,
    )


@router.post("/jobs/{public_id}/evaluate")
async def evaluate_job(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).evaluate(public_id, admin.admin.public_id)


@router.get("/jobs/{public_id}/evaluations")
async def job_evaluations(public_id: str, settings: SettingsDependency):
    return service(settings).evaluations(public_id)


@router.get("/evaluations/{evaluation_public_id}")
async def evaluation(evaluation_public_id: str, settings: SettingsDependency):
    return service(settings).evaluation(evaluation_public_id)


@router.post("/checkpoints/{checkpoint_public_id}/promote")
async def promote_checkpoint(
    checkpoint_public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).promote(checkpoint_public_id, admin.admin.public_id)
