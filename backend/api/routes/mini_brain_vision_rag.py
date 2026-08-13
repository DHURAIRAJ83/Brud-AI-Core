"""MB-17: Brud Mini Brain Vision RAG & Multimodal Retrieval Center --
authenticated admin-only APIs. Independent prefix (`/admin/mini-brain/
vision-rag`), separate from every system this phase reads from (MB-14
Vision Intelligence, MB-15 Vision Model Center, MB-16 Multimodal
Dataset Generator). No route here writes a Dataset Studio record,
edits Document Workspace, starts training, activates a runtime, or
deploys a model -- every mutating route only ever writes to MB-17's
own tables. Every answer is either grounded in real, citable evidence
or honestly reports insufficient evidence -- never fabricated.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06 through MB-16, so every stage is
independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_vision_rag import (
    AdminReviewRequest,
    CorrectResponseRequest,
    CreateSessionRequest,
)
from backend.services.mini_brain_vision_rag_service import MiniBrainVisionRagService

router = APIRouter(
    prefix="/admin/mini-brain/vision-rag",
    tags=["admin-mini-brain-vision-rag"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainVisionRagService:
    return MiniBrainVisionRagService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "dataset_studio_writes_performed": False,
        "document_workspace_writes_performed": False,
        "mb13_writes_performed": False,
        "mb14_writes_performed": False,
        "mb15_writes_performed": False,
        "mb16_writes_performed": False,
        "training_started": False,
        "runtime_activated": False,
        "models_deployed": False,
        "vision_model_inference_performed": False,
        "requires_certified_dataset": True,
        "automatic_approval": False,
        "writes_scope": (
            "own tables only (mini_brain_vision_rag_sessions/_evidence/_events, "
            "mini_brain_vision_rag_memory)"
        ),
        "pipeline_stages": [
            "query_session", "text_retrieval", "ocr_retrieval", "image_retrieval", "object_retrieval",
            "knowledge_graph_retrieval", "evidence_fusion", "grounded_answer", "quality_evaluation",
            "hallucination_check", "report", "awaiting_admin_review", "closed",
        ],
    }


# -- sessions ----------------------------------------------------------------


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_session(
        multimodal_dataset_session_public_id=payload.multimodal_dataset_session_public_id,
        query=payload.query, admin_id=admin.admin.public_id,
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


@router.get("/sessions/{session_id}/evidence")
async def list_evidence(
    session_id: str, settings: SettingsDependency, evidence_type: str | None = None, status: str | None = None,
):
    return service(settings).list_evidence(session_id, evidence_type=evidence_type, status=status)


@router.get("/rag-memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


# -- stages --------------------------------------------------------------------


@router.post("/sessions/{session_id}/text-retrieval")
async def run_text_retrieval(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_text_retrieval_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/ocr-retrieval")
async def run_ocr_retrieval(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_ocr_retrieval_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/image-retrieval")
async def run_image_retrieval(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_image_retrieval_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/object-retrieval")
async def run_object_retrieval(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_object_retrieval_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/knowledge-graph-retrieval")
async def run_knowledge_graph_retrieval(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_knowledge_graph_retrieval_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/evidence-fusion")
async def run_evidence_fusion(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_evidence_fusion_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/answer")
async def run_grounded_answer(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_grounded_answer_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/quality")
async def run_quality_evaluation(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_quality_evaluation_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/hallucination-check")
async def run_hallucination_check(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_hallucination_check_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/correct")
async def correct_response(
    session_id: str, payload: CorrectResponseRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).correct_response(
        session_id, action=payload.action, payload=payload.payload, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review(session_id, decision=payload.decision, admin_id=admin.admin.public_id)
