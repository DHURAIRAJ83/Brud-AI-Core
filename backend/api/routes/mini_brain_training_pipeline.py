"""MB-18: Brud Mini Brain Multimodal Training Pipeline Center --
authenticated admin-only APIs. Independent prefix (`/admin/mini-brain/
training-pipeline`), separate from every system this phase reads from
(MB-05/MB-05.1 Dataset readiness, MB-13 Language Intelligence, MB-14
Vision Intelligence, MB-16 Multimodal Dataset Generator, MB-17 Vision
RAG). No route here starts a training job, calls a training or
quantization API, creates a GGUF file, or deploys/activates a runtime
-- every mutating route only ever writes to MB-18's own tables and its
own artifact directory. Package approval never implies model quality.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06 through MB-17, so every stage is
independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_training_pipeline import (
    AdminReviewRequest,
    CollectDatasetsRequest,
    CollectRagMemoryRequest,
    CreateSessionRequest,
    PlanSplitsRequest,
)
from backend.services.mini_brain_training_pipeline_service import MiniBrainTrainingPipelineService

router = APIRouter(
    prefix="/admin/mini-brain/training-pipeline",
    tags=["admin-mini-brain-training-pipeline"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainTrainingPipelineService:
    return MiniBrainTrainingPipelineService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "training_started": False,
        "torch_training_apis_called": False,
        "transformers_trainer_called": False,
        "accelerate_called": False,
        "llama_cpp_training_apis_called": False,
        "quantization_performed": False,
        "gguf_files_created": False,
        "runtime_activated": False,
        "models_deployed": False,
        "dataset_studio_writes_performed": False,
        "document_workspace_writes_performed": False,
        "mb13_writes_performed": False,
        "mb14_writes_performed": False,
        "mb15_writes_performed": False,
        "mb16_writes_performed": False,
        "mb17_writes_performed": False,
        "model_weights_produced": False,
        "requires_certified_datasets": True,
        "requires_approved_rag_memory": False,
        "automatic_approval": False,
        "writes_scope": (
            "own tables only (mini_brain_training_pipeline_sessions/_events/_memory, "
            "mini_brain_training_packages) plus its own artifact directory on disk"
        ),
        "pipeline_stages": [
            "collect_datasets", "collect_rag_memory", "analyze_language", "analyze_vision",
            "analyze_tokenizer", "plan_splits", "plan_curriculum", "estimate_hardware",
            "build_package", "generate_report", "awaiting_admin_review", "closed",
        ],
    }


# -- sessions ----------------------------------------------------------------


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_session(topic=payload.topic, admin_id=admin.admin.public_id)


@router.get("/sessions")
async def list_sessions(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_sessions(limit=limit, offset=offset)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, settings: SettingsDependency):
    return service(settings).session(session_id)


@router.get("/sessions/{session_id}/events")
async def list_events(
    session_id: str,
    settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).events(session_id, limit=limit, offset=offset)


@router.get("/sessions/{session_id}/packages")
async def list_packages(session_id: str, settings: SettingsDependency):
    return service(settings).list_packages(session_id)


@router.get("/packages/{package_id}")
async def get_package_metadata(package_id: str, settings: SettingsDependency):
    return service(settings).get_package_metadata(package_id)


@router.get("/memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


@router.get("/rag-memory")
async def list_available_rag_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_available_rag_memory(limit=limit, offset=offset)


# -- stages --------------------------------------------------------------------


@router.post("/sessions/{session_id}/collect-datasets")
async def run_collect_datasets(
    session_id: str, payload: CollectDatasetsRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_collect_datasets_stage(
        session_id, dataset_session_public_ids=payload.dataset_session_public_ids,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/collect-rag-memory")
async def run_collect_rag_memory(
    session_id: str, payload: CollectRagMemoryRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_collect_rag_memory_stage(
        session_id, rag_session_public_ids=payload.rag_session_public_ids, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/analyze-language")
async def run_analyze_language(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_analyze_language_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/analyze-vision")
async def run_analyze_vision(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_analyze_vision_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/analyze-tokenizer")
async def run_analyze_tokenizer(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_analyze_tokenizer_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/plan-splits")
async def run_plan_splits(
    session_id: str, payload: PlanSplitsRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_plan_splits_stage(
        session_id, admin_id=admin.admin.public_id, seed=payload.seed,
    )


@router.post("/sessions/{session_id}/plan-curriculum")
async def run_plan_curriculum(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_plan_curriculum_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/estimate-hardware")
async def run_estimate_hardware(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_estimate_hardware_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/build-package")
async def run_build_package(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_build_package_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).admin_review(session_id, decision=payload.decision, admin_id=admin.admin.public_id)
