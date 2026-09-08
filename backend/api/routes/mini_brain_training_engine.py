"""MB-22: Brud Mini Brain Real Training Execution Engine -- authenticated
admin-only APIs. Independent prefix (`/admin/mini-brain/training-engine`),
separate from every system this phase reads from (MB-18 Training
Pipeline, MB-20 Release Governance). No route here deploys a model,
promotes a model to production, calls a Docker/Kubernetes API, exposes
a training API to public users, or writes to Dataset Studio/Document
Workspace/any prior Mini Brain phase's own tables -- every mutating
route only ever writes to MB-22's own tables and its own
`artifacts/training_runs/{job_public_id}/` directory. Every training
job requires its own fresh, per-job admin authorization token recorded
on the job itself before it may start.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06 through MB-21, so every stage is
independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_training_engine import (
    AuthorizeRequest,
    CreateJobRequest,
    ReserveRuntimeRequest,
    SaveCheckpointRequest,
    StreamMetricRequest,
)
from backend.services.mini_brain_training_engine_service import MiniBrainTrainingEngineService

router = APIRouter(
    prefix="/admin/mini-brain/training-engine",
    tags=["admin-mini-brain-training-engine"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainTrainingEngineService:
    return MiniBrainTrainingEngineService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "model_deployed": False,
        "model_promoted_to_production": False,
        "inference_server_started": False,
        "public_chat_started": False,
        "training_api_exposed_to_public_users": False,
        "docker_or_kubernetes_api_called": False,
        "weights_uploaded": False,
        "models_downloaded_automatically": False,
        "shell_commands_executed_from_request_data": False,
        "dataset_studio_writes_performed": False,
        "document_workspace_writes_performed": False,
        "mb16_writes_performed": False,
        "mb17_writes_performed": False,
        "mb18_writes_performed": False,
        "mb19_writes_performed": False,
        "mb20_writes_performed": False,
        "mb21_writes_performed": False,
        "auto_start_after_package_approval": False,
        "requires_fresh_admin_authorization_per_job": True,
        "existing_checkpoints_ever_overwritten": False,
        "simulation_mode_available": True,
        "real_cpu_training_available": False,
        "real_gpu_training_available": False,
        "writes_scope": (
            "own tables only (mini_brain_training_jobs, mini_brain_training_checkpoints, "
            "mini_brain_training_metrics, mini_brain_training_events, "
            "mini_brain_training_engine_memory) plus its own artifacts/training_runs/{job_public_id}/ directory"
        ),
        "workflow_stages": [
            "validate_release", "validate_package", "validate_authorization", "plan_resources",
            "build_manifest", "reserve_runtime", "start_training", "streaming_metrics",
            "generate_report", "awaiting_archive", "cancelled", "archived",
        ],
    }


@router.get("/training-readiness/contract")
async def training_readiness_contract(
    settings: SettingsDependency,
    dataset_version_public_id: str = Query(...),
    core_model_version_public_id: str = Query(...),
    execution_mode: str = Query("gpu"),
):
    """Phase 2.8A: the real, read-only Training Readiness Gate. Reports
    whether this (Dataset Version, Core Model Version, execution_mode)
    combination is qualified to START a controlled training run --
    "READY TO TRAIN", never "ready to release" and never a model-quality
    verdict. No training, checkpoint, activation, release, or Public Chat
    mutation is possible through this route."""

    return service(settings).training_readiness_contract(
        dataset_version_public_id=dataset_version_public_id,
        core_model_version_public_id=core_model_version_public_id,
        execution_mode=execution_mode,
    )


# -- jobs --------------------------------------------------------------------


@router.post("/jobs")
async def create_job(payload: CreateJobRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_job(
        topic=payload.topic, training_package_session_public_id=payload.training_package_session_public_id,
        release_governance_session_public_id=payload.release_governance_session_public_id,
        execution_mode=payload.execution_mode, admin_id=admin.admin.public_id,
        core_model_version_public_id=payload.core_model_version_public_id,
        dataset_version_public_id=payload.dataset_version_public_id,
    )


@router.get("/jobs")
async def list_jobs(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_jobs(limit=limit, offset=offset)


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, settings: SettingsDependency):
    return service(settings).job(job_id)


@router.get("/jobs/{job_id}/events")
async def list_events(
    job_id: str,
    settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).events(job_id, limit=limit, offset=offset)


@router.get("/jobs/{job_id}/checkpoints")
async def list_checkpoints(job_id: str, settings: SettingsDependency):
    return service(settings).list_checkpoints(job_id)


@router.get("/jobs/{job_id}/metrics")
async def list_metrics(
    job_id: str,
    settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_metrics(job_id, limit=limit, offset=offset)


@router.get("/jobs/{job_id}/audit")
async def audit(job_id: str, settings: SettingsDependency):
    return service(settings).audit(job_id)


@router.get("/memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


# -- stages --------------------------------------------------------------------


@router.post("/jobs/{job_id}/validate-release")
async def validate_release(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_validate_release_stage(job_id, admin_id=admin.admin.public_id)


@router.post("/jobs/{job_id}/validate-package")
async def validate_package(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_validate_package_stage(job_id, admin_id=admin.admin.public_id)


@router.post("/jobs/{job_id}/authorize")
async def authorize(job_id: str, payload: AuthorizeRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_validate_authorization_stage(
        job_id, authorization_reason=payload.authorization_reason, admin_id=admin.admin.public_id,
    )


@router.post("/jobs/{job_id}/plan-resources")
async def plan_resources(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_plan_resources_stage(job_id, admin_id=admin.admin.public_id)


@router.post("/jobs/{job_id}/build-manifest")
async def build_manifest(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_build_manifest_stage(job_id, admin_id=admin.admin.public_id)


@router.post("/jobs/{job_id}/reserve-runtime")
async def reserve_runtime(
    job_id: str, settings: SettingsDependency, admin: CsrfDependency,
    # Optional body: simulation/cpu-mode jobs (the overwhelming majority of
    # existing callers, including every pre-Phase-2.7E test) never send one
    # at all -- only a real (execution_mode='gpu') job needs to supply
    # train_blocks/validation_blocks/configuration_label here.
    payload: ReserveRuntimeRequest = ReserveRuntimeRequest(),
):
    return service(settings).run_reserve_runtime_stage(
        job_id, admin_id=admin.admin.public_id, train_blocks=payload.train_blocks,
        validation_blocks=payload.validation_blocks, configuration_label=payload.configuration_label,
    )


@router.post("/jobs/{job_id}/start")
async def start_training(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_start_training_stage(job_id, admin_id=admin.admin.public_id)


@router.post("/jobs/{job_id}/metrics")
async def stream_metric(job_id: str, payload: StreamMetricRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_stream_metric_stage(
        job_id, step=payload.step, epoch=payload.epoch, admin_id=admin.admin.public_id,
    )


@router.post("/jobs/{job_id}/checkpoints")
async def save_checkpoint(job_id: str, payload: SaveCheckpointRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_save_checkpoint_stage(
        job_id, step=payload.step, epoch=payload.epoch, admin_id=admin.admin.public_id,
    )


@router.post("/jobs/{job_id}/pause")
async def pause(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).pause(job_id, admin_id=admin.admin.public_id)


@router.post("/jobs/{job_id}/resume")
async def resume(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).resume(job_id, admin_id=admin.admin.public_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).cancel(job_id, admin_id=admin.admin.public_id)


@router.post("/jobs/{job_id}/finalize")
async def finalize(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).finalize(job_id, admin_id=admin.admin.public_id)


@router.post("/jobs/{job_id}/report")
async def generate_report(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report_stage(job_id, admin_id=admin.admin.public_id)


@router.post("/jobs/{job_id}/archive")
async def archive(job_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).archive(job_id, admin_id=admin.admin.public_id)
