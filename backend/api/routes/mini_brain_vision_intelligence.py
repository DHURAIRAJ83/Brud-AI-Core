"""MB-14: Brud Mini Brain Vision Intelligence & Image Understanding
Center -- authenticated admin-only APIs. Independent prefix
(`/admin/mini-brain/vision-intelligence`), separate from every system
this phase reads from (Document Workspace, Task Finalization's content
classification). No route here writes a dataset record, starts
training, activates a runtime, exports GGUF, modifies RAG, or deploys
a model -- every mutating route only ever writes to MB-14's own
tables.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06/MB-09/MB-10/MB-11/MB-12/MB-13, so
every stage is independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_vision_intelligence import (
    AdminReviewRequest,
    AnnotateRequest,
    CreateSessionRequest,
    RunCaptionRequest,
    RunOcrCrossValidationRequest,
)
from backend.services.mini_brain_vision_intelligence_service import (
    MiniBrainVisionIntelligenceService,
)

router = APIRouter(
    prefix="/admin/mini-brain/vision-intelligence",
    tags=["admin-mini-brain-vision-intelligence"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainVisionIntelligenceService:
    return MiniBrainVisionIntelligenceService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "vision_model_available": False,
        "object_detection_model_available": False,
        "captioning_model_available": False,
        "dataset_writes_performed": False,
        "training_started": False,
        "runtime_activated": False,
        "gguf_exported": False,
        "rag_modified": False,
        "models_deployed": False,
        "automatic_approval": False,
        "writes_scope": (
            "own tables only (mini_brain_vision_sessions/_images/_objects/_events) plus "
            "extracted image files under document_dir/vision/<session>/"
        ),
        "pipeline_stages": [
            "image_extraction", "image_quality", "vision_understanding", "ocr_cross_validation",
            "caption_generation", "bounding_box_planning", "admin_annotation", "knowledge_graph",
            "qa_generation", "vision_dataset_draft", "vision_quality_score", "vision_report",
            "awaiting_admin_review", "certified", "closed",
        ],
    }


# -- sessions ----------------------------------------------------------------


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_session(
        document_source_public_id=payload.document_source_public_id,
        dataset_source_public_id=payload.dataset_source_public_id, admin_id=admin.admin.public_id,
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


@router.get("/sessions/{session_id}/images")
async def list_images(session_id: str, settings: SettingsDependency):
    return service(settings).list_images(session_id)


@router.get("/sessions/{session_id}/objects")
async def list_objects(session_id: str, settings: SettingsDependency, status: str | None = None):
    return service(settings).list_objects(session_id, status=status)


# -- stages --------------------------------------------------------------------


@router.post("/sessions/{session_id}/image-extraction")
async def run_image_extraction(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_image_extraction_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/image-quality")
async def run_image_quality(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_image_quality_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/vision-understanding")
async def run_vision_understanding(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_vision_understanding_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/ocr-cross-validation")
async def run_ocr_cross_validation(
    session_id: str, payload: RunOcrCrossValidationRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).run_ocr_cross_validation_stage(
        session_id, admin_id=admin.admin.public_id, dataset_text=payload.dataset_text,
        language_report_status=payload.language_report_status,
    )


@router.post("/sessions/{session_id}/caption")
async def run_caption(
    session_id: str, payload: RunCaptionRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).run_caption_stage(
        session_id, admin_id=admin.admin.public_id, admin_caption=payload.admin_caption,
    )


@router.post("/sessions/{session_id}/bounding-box-plan")
async def run_bounding_box_plan(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_bounding_box_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/annotate")
async def annotate(
    session_id: str, payload: AnnotateRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).annotate(
        session_id, action=payload.action, object_public_id=payload.object_public_id,
        payload=payload.payload, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/annotation/finish")
async def finish_annotation(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).finish_annotation_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/knowledge-graph")
async def run_knowledge_graph(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_knowledge_graph_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/qa-generation")
async def run_qa_generation(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_qa_generation_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/dataset-draft")
async def run_dataset_draft(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_dataset_draft_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/quality-score")
async def run_quality_score(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_quality_score_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review(session_id, decision=payload.decision, admin_id=admin.admin.public_id)
