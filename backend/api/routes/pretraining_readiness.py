"""Phase 21A production tokenizer and base-model pretraining
readiness admin API. Every mutation requires admin authentication and
CSRF. Nothing in this router starts long-running or production-scale
training -- the only training that runs here is the tiny, bounded
pretraining smoke test, and no route wires any result into the public
chatbot.
"""

from typing import Any

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.core_models import CoreModelRepository
from backend.database.repositories.corpus import CorpusRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.pretraining_readiness import PretrainingReadinessRepository
from backend.models.pretraining_readiness import (
    BaseModelReadinessEvaluationCreate,
    PretrainingSnapshotCreate,
    ResourceEstimateCreate,
    SmokeRunCreate,
    TokenizerApprovalRequest,
    TokenizerCandidateComparisonCreate,
    TokenizerCorpusBuildCreate,
    TrainingConfigValidateRequest,
)
from backend.services.base_model_readiness_service import BaseModelReadinessService
from backend.services.base_model_resource_service import BaseModelResourceService
from backend.services.pretraining_smoke_service import PretrainingSmokeService
from backend.services.pretraining_snapshot_service import PretrainingSnapshotService
from backend.services.tokenizer_candidate_service import TokenizerCandidateService
from backend.services.tokenizer_corpus_service import TokenizerCorpusService

router = APIRouter(
    prefix="/admin/pretraining-readiness", tags=["admin-pretraining-readiness"],
    dependencies=[Depends(require_admin)],
)


def _readiness_repo(settings) -> PretrainingReadinessRepository:
    return PretrainingReadinessRepository(settings.resolved_database_path)


def _corpus_repo(settings) -> CorpusRepository:
    return CorpusRepository(settings.resolved_database_path)


def tokenizer_corpus_service(settings) -> TokenizerCorpusService:
    return TokenizerCorpusService(_corpus_repo(settings), _readiness_repo(settings), settings)


def tokenizer_candidate_service(settings) -> TokenizerCandidateService:
    return TokenizerCandidateService(_readiness_repo(settings), settings)


def resource_service(settings) -> BaseModelResourceService:
    return BaseModelResourceService(_readiness_repo(settings), settings)


def snapshot_service(settings) -> PretrainingSnapshotService:
    return PretrainingSnapshotService(_corpus_repo(settings), _readiness_repo(settings), settings)


def smoke_service(settings) -> PretrainingSmokeService:
    return PretrainingSmokeService(
        _readiness_repo(settings),
        CoreModelRepository(settings.resolved_database_path),
        PretrainingRepository(settings.resolved_database_path),
        settings,
    )


def readiness_gate_service(settings) -> BaseModelReadinessService:
    return BaseModelReadinessService(
        _readiness_repo(settings),
        _corpus_repo(settings),
        PretrainingRepository(settings.resolved_database_path),
        settings,
    )


# --- tokenizer corpus -----------------------------------------------------


@router.get("/tokenizer-corpus-builds")
async def list_tokenizer_corpus_builds(settings: SettingsDependency):
    return tokenizer_corpus_service(settings).list_builds()


@router.post("/tokenizer-corpus-builds")
async def create_tokenizer_corpus_build(
    payload: TokenizerCorpusBuildCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return tokenizer_corpus_service(settings).build_corpus(payload, admin.admin.public_id)


@router.get("/tokenizer-corpus-builds/{public_id}")
async def get_tokenizer_corpus_build(public_id: str, settings: SettingsDependency):
    return tokenizer_corpus_service(settings).get_build(public_id)


# --- tokenizer candidates -----------------------------------------------------


@router.post("/tokenizer-candidate-comparisons")
async def create_tokenizer_candidate_comparison(
    payload: TokenizerCandidateComparisonCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return tokenizer_candidate_service(settings).create_comparison(payload, admin.admin.public_id)


@router.get("/tokenizer-candidate-comparisons/{public_id}")
async def get_tokenizer_candidate_comparison(public_id: str, settings: SettingsDependency):
    return tokenizer_candidate_service(settings).get_comparison(public_id)


@router.post("/tokenizer-candidate-comparisons/{public_id}/approve")
async def approve_tokenizer_candidate(
    public_id: str, payload: TokenizerApprovalRequest, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return tokenizer_candidate_service(settings).approve(public_id, payload, admin.admin.public_id)


@router.post("/tokenizer-versions/{public_id}/activate")
async def activate_tokenizer_version(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return tokenizer_candidate_service(settings).activate(public_id, admin.admin.public_id)


# --- resource estimates -----------------------------------------------------


@router.get("/resource-estimates")
async def list_resource_estimates(settings: SettingsDependency):
    return resource_service(settings).list_estimates()


@router.post("/resource-estimates")
async def create_resource_estimate(
    payload: ResourceEstimateCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return resource_service(settings).create_estimate(payload, admin.admin.public_id)


@router.get("/resource-estimates/{public_id}")
async def get_resource_estimate(public_id: str, settings: SettingsDependency):
    return resource_service(settings).get_estimate(public_id)


# --- pretraining dataset snapshots -----------------------------------------------------


@router.get("/dataset-snapshots")
async def list_dataset_snapshots(settings: SettingsDependency):
    return snapshot_service(settings).list_snapshots()


@router.post("/dataset-snapshots")
async def create_dataset_snapshot(
    payload: PretrainingSnapshotCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return snapshot_service(settings).create_snapshot(payload, admin.admin.public_id)


@router.get("/dataset-snapshots/{public_id}")
async def get_dataset_snapshot(public_id: str, settings: SettingsDependency):
    return snapshot_service(settings).get_snapshot(public_id)


# --- training configuration + smoke runs -----------------------------------------------------


@router.post("/training-config/validate")
async def validate_training_config(
    payload: TrainingConfigValidateRequest, settings: SettingsDependency
) -> dict[str, Any]:
    return smoke_service(settings).validate_training_config(payload)


@router.get("/smoke-runs")
async def list_smoke_runs(settings: SettingsDependency):
    return smoke_service(settings).list_smoke_runs()


@router.post("/smoke-runs")
async def create_smoke_run(
    payload: SmokeRunCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return smoke_service(settings).create_smoke_run(payload, admin.admin.public_id)


@router.get("/smoke-runs/{public_id}")
async def get_smoke_run(public_id: str, settings: SettingsDependency):
    return smoke_service(settings).get_smoke_run(public_id)


# --- base-model readiness gate -----------------------------------------------------


@router.get("/readiness-evaluations")
async def list_readiness_evaluations(settings: SettingsDependency):
    return readiness_gate_service(settings).list_evaluations()


@router.post("/readiness-evaluations")
async def create_readiness_evaluation(
    payload: BaseModelReadinessEvaluationCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return readiness_gate_service(settings).evaluate(payload, admin.admin.public_id)


@router.get("/readiness-evaluations/{public_id}")
async def get_readiness_evaluation(public_id: str, settings: SettingsDependency):
    return readiness_gate_service(settings).get_evaluation(public_id)
