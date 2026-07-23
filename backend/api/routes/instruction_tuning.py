"""Phase 12 instruction-tuning experiment APIs."""

from fastapi import APIRouter, Depends, Query

from backend.api.auth import AdminDependency, CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.instruction_tuning import InstructionTuningRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.models.instruction_tuning import (
    DiagnosticGenerateRequest,
    InstructionCandidateSelectionRequest,
    InstructionTemplateCreate,
    InstructionTuningExperimentCreate,
    InstructionTuningExperimentPatch,
    InstructionTuningRunCompareRequest,
    InstructionTuningRunCreate,
)
from backend.services.instruction_tuning_service import InstructionTuningService

router = APIRouter(
    prefix="/admin/instruction-tuning",
    tags=["admin-instruction-tuning"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> InstructionTuningService:
    return InstructionTuningService(
        InstructionTuningRepository(settings.resolved_database_path),
        PretrainingRepository(settings.resolved_database_path),
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
    payload: InstructionTuningExperimentCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_experiment(payload, admin.admin.public_id)


@router.get("/experiments/{public_id}")
async def experiment(public_id: str, settings: SettingsDependency):
    return service(settings).get_experiment(public_id)


@router.patch("/experiments/{public_id}")
async def patch_experiment(
    public_id: str,
    payload: InstructionTuningExperimentPatch,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).patch_experiment(public_id, payload, admin.admin.public_id)


# --- dataset profile -----------------------------------------------------


@router.post("/experiments/{public_id}/profile")
async def generate_profile(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_profile(public_id, admin.admin.public_id)


@router.get("/experiments/{public_id}/profile")
async def profile(public_id: str, settings: SettingsDependency):
    return service(settings).get_profile(public_id)


# --- templates -----------------------------------------------------


@router.get("/templates")
async def templates(settings: SettingsDependency):
    return service(settings).list_templates()


@router.post("/templates")
async def create_template(
    payload: InstructionTemplateCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_template(payload, admin.admin.public_id)


@router.get("/templates/{public_id}")
async def template(public_id: str, settings: SettingsDependency):
    return service(settings).get_template(public_id)


@router.post("/templates/{public_id}/validate")
async def validate_template(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).validate_template(public_id, admin.admin.public_id)


# --- runs -----------------------------------------------------


@router.post("/experiments/{public_id}/runs")
async def create_run(
    public_id: str,
    payload: InstructionTuningRunCreate,
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


# --- metrics and checks -----------------------------------------------------


@router.get("/runs/{run_public_id}/metrics")
async def metrics(run_public_id: str, settings: SettingsDependency):
    return service(settings).metrics(run_public_id)


@router.get("/runs/{run_public_id}/language-metrics")
async def language_metrics(run_public_id: str, settings: SettingsDependency):
    return service(settings).language_metrics(run_public_id)


@router.get("/runs/{run_public_id}/learning-checks")
async def learning_checks(run_public_id: str, settings: SettingsDependency):
    return service(settings).learning_checks_for_run(run_public_id)


# --- diagnostic generation -----------------------------------------------------


@router.post("/runs/{run_public_id}/diagnostic-generate")
async def diagnostic_generate(
    run_public_id: str,
    payload: DiagnosticGenerateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
):
    return service(settings).diagnostic_generate(
        run_public_id, payload.prompt_text, payload.max_new_tokens, admin.admin.public_id
    )


# --- comparisons -----------------------------------------------------


@router.post("/experiments/{public_id}/compare-runs")
async def compare_runs(
    public_id: str,
    payload: InstructionTuningRunCompareRequest,
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
    payload: InstructionCandidateSelectionRequest | None = None,
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
