"""Phase 13 multilingual evaluation, safety validation, and chat-readiness APIs."""

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.model_evaluation import ModelEvaluationRepository
from backend.models.model_evaluation import (
    HumanReviewCreate,
    ModelEvaluationComparisonCreate,
    ModelEvaluationFixtureSetCreate,
    ModelEvaluationRunCreate,
    ModelEvaluationSuiteCreate,
    ModelEvaluationSuitePatch,
)
from backend.services.model_evaluation_service import ModelEvaluationService

router = APIRouter(
    prefix="/admin/model-evaluation",
    tags=["admin-model-evaluation"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> ModelEvaluationService:
    return ModelEvaluationService(
        ModelEvaluationRepository(settings.resolved_database_path), settings
    )


# --- candidates -----------------------------------------------------


@router.get("/candidates")
async def eligible_candidates(settings: SettingsDependency):
    return service(settings).eligible_candidates()


# --- suites -----------------------------------------------------


@router.get("/suites")
async def suites(settings: SettingsDependency):
    return service(settings).list_suites()


@router.post("/suites")
async def create_suite(
    payload: ModelEvaluationSuiteCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_suite(payload, admin.admin.public_id)


@router.get("/suites/{public_id}")
async def suite(public_id: str, settings: SettingsDependency):
    return service(settings).get_suite(public_id)


@router.patch("/suites/{public_id}")
async def patch_suite(
    public_id: str,
    payload: ModelEvaluationSuitePatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_suite(public_id, payload, admin.admin.public_id)


@router.post("/suites/{public_id}/validate")
async def validate_suite(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).validate_suite(public_id, admin.admin.public_id)


@router.post("/suites/{public_id}/activate")
async def activate_suite(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).activate_suite(public_id, admin.admin.public_id)


# --- fixture sets / fixtures -----------------------------------------------------


@router.get("/suites/{public_id}/fixture-sets")
async def fixture_sets(public_id: str, settings: SettingsDependency):
    return service(settings).list_fixture_sets(public_id)


@router.post("/suites/{public_id}/fixture-sets")
async def create_fixture_set(
    public_id: str,
    payload: ModelEvaluationFixtureSetCreate,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).create_fixture_set(public_id, payload, admin.admin.public_id)


@router.get("/fixture-sets/{public_id}")
async def fixture_set(public_id: str, settings: SettingsDependency):
    return service(settings).get_fixture_set(public_id)


@router.get("/fixture-sets/{public_id}/coverage")
async def fixture_set_coverage(public_id: str, settings: SettingsDependency):
    return service(settings).fixture_set_coverage(public_id)


@router.get("/fixture-sets/{public_id}/fixtures")
async def fixtures(public_id: str, settings: SettingsDependency):
    return service(settings).list_fixtures(public_id)


# --- runs -----------------------------------------------------


@router.get("/runs")
async def runs(settings: SettingsDependency):
    return service(settings).list_runs()


@router.post("/runs")
async def create_run(
    payload: ModelEvaluationRunCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_run(payload, admin.admin.public_id)


@router.get("/runs/{run_public_id}")
async def run(run_public_id: str, settings: SettingsDependency):
    return service(settings).get_run(run_public_id)


@router.post("/runs/{run_public_id}/execute")
async def execute_run(run_public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).execute_run(run_public_id, admin.admin.public_id)


@router.get("/runs/{run_public_id}/outputs")
async def outputs(run_public_id: str, settings: SettingsDependency):
    return service(settings).outputs_for_run(run_public_id)


@router.get("/runs/{run_public_id}/metrics")
async def metrics(run_public_id: str, settings: SettingsDependency):
    return service(settings).metrics_for_run(run_public_id)


@router.get("/runs/{run_public_id}/issues")
async def issues(run_public_id: str, settings: SettingsDependency):
    return service(settings).issues_for_run(run_public_id)


# --- human review -----------------------------------------------------


@router.post("/human-reviews")
async def submit_review(
    payload: HumanReviewCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).submit_review(payload, admin.admin.public_id)


@router.get("/runs/{run_public_id}/review-queue")
async def review_queue(run_public_id: str, settings: SettingsDependency):
    return service(settings).review_queue(run_public_id)


@router.get("/runs/{run_public_id}/reviews")
async def reviews(run_public_id: str, settings: SettingsDependency):
    return service(settings).reviews_for_run(run_public_id)


# --- chat readiness -----------------------------------------------------


@router.post("/runs/{run_public_id}/assess-readiness")
async def assess_readiness(run_public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).assess_readiness(run_public_id, admin.admin.public_id)


@router.get("/runs/{run_public_id}/readiness")
async def readiness(run_public_id: str, settings: SettingsDependency):
    return service(settings).latest_readiness(run_public_id)


# --- comparisons -----------------------------------------------------


@router.post("/comparisons")
async def compare_runs(
    payload: ModelEvaluationComparisonCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).compare_runs(payload, admin.admin.public_id)


# --- reproducibility -----------------------------------------------------


@router.post("/runs/{run_public_id}/manifest")
async def generate_manifest(
    run_public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).generate_manifest(run_public_id, admin.admin.public_id)


@router.post("/runs/{run_public_id}/manifest/verify")
async def verify_manifest(run_public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).verify_manifest(run_public_id)
