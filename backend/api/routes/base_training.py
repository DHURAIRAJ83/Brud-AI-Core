"""Phase 11 base-training experiment APIs."""

from fastapi import APIRouter, Depends, Query

from backend.api.auth import AdminDependency, CsrfDependency, require_admin
from backend.api.dependencies import PoolDependency, SettingsDependency
from backend.database.connection_pool import ConnectionPool
from backend.database.repositories.base_training import BaseTrainingRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.models.base_training import (
    BaseTrainingExperimentCreate,
    BaseTrainingExperimentPatch,
    BaseTrainingRunCompareRequest,
    BaseTrainingRunCreate,
    CandidateSelectionRequest,
)
from backend.services.base_training_service import BaseTrainingService

router = APIRouter(
    prefix="/admin/base-training",
    tags=["admin-base-training"],
    dependencies=[Depends(require_admin)],
)


def service(settings, pool: ConnectionPool | None = None) -> BaseTrainingService:
    """Phase 7C-33/7C-34: `pool` defaults to `None`, so every existing call
    site below that still says `service(settings)` (unchanged) keeps
    today's exact unpooled behavior. `experiment()`/`create_experiment()`
    (Phase 7C-33) and `generate_profile()`/`tokenizer_evaluate()`
    (Phase 7C-34) were opted into the shared app-instance pool (via
    `PoolDependency`, which resolves to `None` for any app instance that
    never went through `create_app()`'s lifespan override) -- the latter
    two deliberately chosen because they reach the previously-fixed
    TokenizerService nested chains (`processor_for_version`/
    `evaluate_suitability`, Phase 7C-20/7C-22) via `connection=` propagation,
    proving that fix still holds when the outer connection comes from a
    real pool. This is not a signal that the rest of this file needs
    converting in one phase -- remaining routes are deliberately left
    unpooled pending their own evidence."""

    return BaseTrainingService(
        BaseTrainingRepository(settings.resolved_database_path, pool=pool),
        PretrainingRepository(settings.resolved_database_path, pool=pool),
        settings,
    )


# --- experiments -----------------------------------------------------


@router.get("/experiments")
async def experiments(
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    return service(settings).list_experiments(page, page_size)


@router.post("/experiments")
async def create_experiment(
    payload: BaseTrainingExperimentCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
    pool: PoolDependency,
):
    return service(settings, pool).create_experiment(payload, admin.admin.public_id)


@router.get("/experiments/{public_id}")
async def experiment(public_id: str, settings: SettingsDependency, pool: PoolDependency):
    return service(settings, pool).get_experiment(public_id)


@router.patch("/experiments/{public_id}")
async def patch_experiment(
    public_id: str,
    payload: BaseTrainingExperimentPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_experiment(public_id, payload, admin.admin.public_id)


# --- dataset profile -----------------------------------------------------


@router.post("/experiments/{public_id}/profile")
async def generate_profile(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency, pool: PoolDependency
):
    return service(settings, pool).generate_profile(public_id, admin.admin.public_id)


@router.get("/experiments/{public_id}/profile")
async def profile(public_id: str, settings: SettingsDependency):
    return service(settings).get_profile(public_id)


# --- tokenizer evaluation -----------------------------------------------------


@router.post("/experiments/{public_id}/tokenizer-evaluate")
async def tokenizer_evaluate(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency, pool: PoolDependency
):
    return service(settings, pool).evaluate_tokenizer(public_id, admin.admin.public_id)


@router.get("/experiments/{public_id}/tokenizer-evaluation")
async def tokenizer_evaluation(public_id: str, settings: SettingsDependency):
    return service(settings).get_tokenizer_evaluation(public_id)


# --- runs -----------------------------------------------------


@router.post("/experiments/{public_id}/runs")
async def create_run(
    public_id: str,
    payload: BaseTrainingRunCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).create_run(public_id, payload, admin.admin.public_id)


@router.get("/experiments/{public_id}/runs")
async def runs(public_id: str, settings: SettingsDependency):
    return service(settings).list_runs(public_id)


@router.get("/runs/{run_public_id}")
async def run(run_public_id: str, settings: SettingsDependency):
    return service(settings).get_run(run_public_id)


@router.post("/runs/{run_public_id}/queue")
async def queue_run(run_public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).queue_run(run_public_id, admin.admin.public_id)


@router.post("/runs/{run_public_id}/evaluate")
async def evaluate_run(run_public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).evaluate_run(run_public_id, admin.admin.public_id)


# --- metrics -----------------------------------------------------


@router.get("/runs/{run_public_id}/language-metrics")
async def language_metrics(run_public_id: str, settings: SettingsDependency):
    return service(settings).language_metrics(run_public_id)


@router.get("/runs/{run_public_id}/learning-checks")
async def learning_checks(run_public_id: str, settings: SettingsDependency):
    return service(settings).learning_checks_for_run(run_public_id)


# --- comparisons -----------------------------------------------------


@router.post("/experiments/{public_id}/compare-runs")
async def compare_runs(
    public_id: str,
    payload: BaseTrainingRunCompareRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).compare_runs(
        public_id, payload.left_run_public_id, payload.right_run_public_id, admin.admin.public_id
    )


@router.get("/experiments/{public_id}/comparisons")
async def comparisons(public_id: str, settings: SettingsDependency):
    return service(settings).comparisons(public_id)


# --- candidate selection -----------------------------------------------------


@router.post("/experiments/{public_id}/select-candidate")
async def select_candidate(
    public_id: str,
    settings: SettingsDependency,
    admin: CsrfDependency,
    payload: CandidateSelectionRequest | None = None,
):
    override_comment = payload.override_comment if payload else None
    return service(settings).select_candidate(public_id, override_comment, admin.admin.public_id)


@router.get("/experiments/{public_id}/candidate")
async def candidate(public_id: str, settings: SettingsDependency):
    return service(settings).candidate(public_id)


# --- reproducibility -----------------------------------------------------


@router.get("/experiments/{public_id}/manifest")
async def manifest(public_id: str, settings: SettingsDependency, admin: AdminDependency):
    return service(settings).generate_manifest(public_id, admin.admin.public_id)


@router.post("/experiments/{public_id}/manifest/verify")
async def manifest_verify(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).verify_manifest(public_id)
