"""Phase 10 training-reliability APIs: workers, coverage, recovery, quality, retention."""

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.base import NotFoundError
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.training_reliability import (
    TrainingReliabilityRepository,
    public_row,
)
from backend.models.training_reliability import (
    RecoveryRequest,
    RetentionApplyRequest,
    RunComparisonRequest,
)
from backend.services.pretraining_reliability_service import PretrainingReliabilityService
from backend.services.training_evaluation_service import TrainingEvaluationService
from backend.services.worker_recovery_service import WorkerRecoveryService

router = APIRouter(
    prefix="/admin/pretraining",
    tags=["admin-pretraining-reliability"],
    dependencies=[Depends(require_admin)],
)


def _reliability(settings) -> TrainingReliabilityRepository:
    return TrainingReliabilityRepository(settings.resolved_database_path)


def worker_service(settings) -> PretrainingReliabilityService:
    return PretrainingReliabilityService(_reliability(settings))


def recovery_service(settings) -> WorkerRecoveryService:
    return WorkerRecoveryService(
        PretrainingRepository(settings.resolved_database_path), _reliability(settings), settings
    )


def evaluation_service(settings) -> TrainingEvaluationService:
    return TrainingEvaluationService(
        PretrainingRepository(settings.resolved_database_path), _reliability(settings), settings
    )


# --- workers -----------------------------------------------------


@router.get("/workers")
async def workers(settings: SettingsDependency):
    return worker_service(settings).workers()


@router.get("/workers/{worker_public_id}")
async def worker(worker_public_id: str, settings: SettingsDependency):
    return worker_service(settings).worker(worker_public_id)


# --- coverage and streams -----------------------------------------------------


@router.post("/jobs/{public_id}/coverage")
async def generate_coverage(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return evaluation_service(settings).generate_coverage(public_id, admin.admin.public_id)


@router.get("/jobs/{public_id}/coverage")
async def coverage(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).coverage(public_id)


@router.get("/jobs/{public_id}/streams")
async def streams(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).streams(public_id)


@router.post("/jobs/{public_id}/streams/verify")
async def verify_streams(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return evaluation_service(settings).verify_streams(public_id, admin.admin.public_id)


# --- recovery -----------------------------------------------------


@router.get("/recovery/stale-jobs")
async def stale_jobs(settings: SettingsDependency):
    return recovery_service(settings).stale_jobs()


@router.post("/jobs/{public_id}/recover")
async def recover_job(
    public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
    payload: RecoveryRequest | None = None,
):
    service = recovery_service(settings)
    with service.repository.transaction() as connection:
        job = service.repository.job(connection, public_id)
    recovery_type = "stale_lease" if job["recovery_required"] else "manual_resume"
    comment = payload.comment if payload else None
    return service.recover(public_id, admin.admin.public_id, recovery_type, comment)


@router.get("/jobs/{public_id}/recoveries")
async def job_recoveries(public_id: str, settings: SettingsDependency):
    return recovery_service(settings).recoveries(public_id)


@router.get("/recoveries/{recovery_public_id}")
async def recovery(recovery_public_id: str, settings: SettingsDependency):
    return recovery_service(settings).recovery(recovery_public_id)


# --- summary and quality -----------------------------------------------------


@router.get("/jobs/{public_id}/summary")
async def run_summary(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).run_summary(public_id)


@router.post("/jobs/{public_id}/quality/assess")
async def assess_quality(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return evaluation_service(settings).assess_quality(public_id, admin.admin.public_id)


@router.get("/jobs/{public_id}/quality")
async def quality(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).quality(public_id)


@router.get("/jobs/{public_id}/quality/issues")
async def quality_issues(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).quality_issues(public_id)


# --- comparisons -----------------------------------------------------


@router.post("/jobs/compare")
async def compare_runs(
    payload: RunComparisonRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return evaluation_service(settings).compare_runs(
        payload.left_job_public_id, payload.right_job_public_id, admin.admin.public_id
    )


@router.get("/comparisons/{public_id}")
async def comparison(public_id: str, settings: SettingsDependency):
    reliability = _reliability(settings)
    with reliability.transaction() as connection:
        try:
            row = reliability.checkpoint_comparison(connection, public_id)
            return public_row(row)
        except NotFoundError:
            pass
        row = reliability.run_comparison(connection, public_id)
        return public_row(row)


# --- retention -----------------------------------------------------


@router.post("/jobs/{public_id}/retention/preview")
async def retention_preview(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return evaluation_service(settings).retention_preview(public_id, admin.admin.public_id)


@router.post("/jobs/{public_id}/retention/apply")
async def retention_apply(
    public_id: str,
    payload: RetentionApplyRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return evaluation_service(settings).retention_apply(
        public_id, payload.checkpoint_public_ids, admin.admin.public_id
    )
