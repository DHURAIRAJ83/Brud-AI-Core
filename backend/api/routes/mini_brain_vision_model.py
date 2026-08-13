"""MB-15: Brud Mini Brain Vision Model Integration & Human-in-the-Loop
Annotation Center -- authenticated admin-only APIs. Independent prefix
(`/admin/mini-brain/vision-model`), separate from every system this
phase reads from (MB-14 Vision Intelligence, MB-13 Language
Intelligence, Document Workspace). No route here writes a dataset
record, starts training, activates a runtime, exports GGUF, modifies
RAG, deploys a model, or edits MB-14/MB-06/MB-07 -- every mutating
route only ever writes to MB-15's own tables.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06 through MB-14, so every stage is
independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_vision_model import (
    AdminReviewRequest,
    CreateSessionRequest,
    OcrCrossValidationRequest,
    ProviderSelectionRequest,
    ProviderStatusRequest,
    ReviewPredictionRequest,
)
from backend.services.mini_brain_vision_model_service import MiniBrainVisionModelService

router = APIRouter(
    prefix="/admin/mini-brain/vision-model",
    tags=["admin-mini-brain-vision-model"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainVisionModelService:
    return MiniBrainVisionModelService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "vision_model_file_present": False,
        "backend_library_available": {"onnx": False, "openvino": False, "llava_gguf": True},
        "dataset_writes_performed": False,
        "document_writes_performed": False,
        "mb14_writes_performed": False,
        "training_started": False,
        "runtime_activated": False,
        "gguf_exported": False,
        "rag_modified": False,
        "mb06_modified": False,
        "mb07_modified": False,
        "models_deployed": False,
        "automatic_approval": False,
        "writes_scope": (
            "own tables only (mini_brain_vision_model_sessions/_predictions/_events, "
            "mini_brain_vision_correction_memory, mini_brain_vision_learning_memory, "
            "mini_brain_vision_provider_registry)"
        ),
        "pipeline_stages": [
            "image_load", "provider_selection", "object_detection", "scene_detection",
            "caption_generation", "relationship_detection", "ocr_cross_validation", "quality_score",
            "admin_review", "correction_memory", "knowledge_graph", "dataset_draft", "vision_report",
            "awaiting_admin_review", "certified", "closed",
        ],
    }


# -- provider registry ---------------------------------------------------------


@router.get("/providers")
async def list_providers(settings: SettingsDependency, status: str | None = None):
    return service(settings).list_providers(status=status)


@router.post("/providers/{provider_key}/status")
async def set_provider_status(
    provider_key: str, payload: ProviderStatusRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).set_provider_status(provider_key, status=payload.status, admin_id=admin.admin.public_id)


# -- sessions ----------------------------------------------------------------


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_session(
        vision_session_public_id=payload.vision_session_public_id,
        language_session_public_id=payload.language_session_public_id, provider_key=payload.provider_key,
        admin_id=admin.admin.public_id,
    )


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


@router.get("/sessions/{session_id}/predictions")
async def list_predictions(session_id: str, settings: SettingsDependency, review_status: str | None = None):
    return service(settings).list_predictions(session_id, review_status=review_status)


@router.get("/sessions/{session_id}/corrections")
async def list_corrections(session_id: str, settings: SettingsDependency):
    return service(settings).list_corrections(session_id)


@router.get("/learning-memory")
async def list_learning_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_learning_memory(limit=limit, offset=offset)


# -- stages --------------------------------------------------------------------


@router.post("/sessions/{session_id}/image-load")
async def run_image_load(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_image_load_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/provider-selection")
async def run_provider_selection(
    session_id: str, payload: ProviderSelectionRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).run_provider_selection_stage(
        session_id, admin_id=admin.admin.public_id, model_path=payload.model_path,
        mmproj_path=payload.mmproj_path, context_length=payload.context_length,
    )


@router.post("/sessions/{session_id}/object-detection")
async def run_object_detection(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_object_detection_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/scene-detection")
async def run_scene_detection(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_scene_detection_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/caption")
async def run_caption(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_caption_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/relationship-detection")
async def run_relationship_detection(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_relationship_detection_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/ocr-cross-validation")
async def run_ocr_cross_validation(
    session_id: str, payload: OcrCrossValidationRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).run_ocr_cross_validation_stage(
        session_id, admin_id=admin.admin.public_id, dataset_text=payload.dataset_text,
    )


@router.post("/sessions/{session_id}/quality-score")
async def run_quality_score(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_quality_score_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/review")
async def review_prediction(
    session_id: str, payload: ReviewPredictionRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).review_prediction(
        session_id, action=payload.action, prediction_public_id=payload.prediction_public_id,
        payload=payload.payload, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/review/finish")
async def finish_admin_review(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).finish_admin_review_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/correction-memory")
async def run_correction_memory(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_correction_memory_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/knowledge-graph")
async def run_knowledge_graph(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_knowledge_graph_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/dataset-draft")
async def run_dataset_draft(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_dataset_draft_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review(session_id, decision=payload.decision, admin_id=admin.admin.public_id)
