"""MB-11: Brud Mini Brain Autonomous Dataset Evolution & Knowledge
Factory -- authenticated admin-only APIs. Independent prefix
(`/admin/mini-brain/dataset-evolution`), separate from every system
this phase reads from (MB-05, MB-05.1, MB-08, MB-09, MB-10, the
duplicate-detection service, RAG Sandbox). No route here writes a
dataset record, starts training, deploys a model, activates a runtime,
or modifies RAG -- every mutating route only ever writes to MB-11's
own tables (or, for the RAG Sandbox generation/evaluation routes, to
RAG Sandbox's own tables through its own existing service methods,
exactly as MB-06/MB-10 already do).

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06/MB-09/MB-10, so every stage is
independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_dataset_evolution import (
    AdminReviewRequest,
    CreateSessionRequest,
    RagAdminReviewRequest,
    RunRagEvaluationRequest,
)
from backend.services.mini_brain_dataset_evolution_service import MiniBrainDatasetEvolutionService

router = APIRouter(
    prefix="/admin/mini-brain/dataset-evolution",
    tags=["admin-mini-brain-dataset-evolution"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainDatasetEvolutionService:
    return MiniBrainDatasetEvolutionService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "ai_model_used": False,
        "dataset_writes_performed": False,
        "training_started": False,
        "models_deployed": False,
        "rag_modified": False,
        "writes_scope": (
            "own tables only (mini_brain_dataset_evolution_sessions/_events); RAG Sandbox "
            "generation/evaluation/report routes write to RAG Sandbox's own tables through its own "
            "existing service methods, exactly as MB-06/MB-10 do"
        ),
        "pipeline_stages": [
            "knowledge_evolution", "dataset_evolution", "evolution_simulation", "recommendation",
            "awaiting_admin_review", "rag_evaluation", "awaiting_rag_review", "closed",
        ],
    }


# -- sessions ----------------------------------------------------------------


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_session(
        dataset_source_public_id=payload.dataset_source_public_id, admin_id=admin.admin.public_id,
    )


@router.get("/sessions")
async def list_sessions(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=200),
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
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).events(session_id, limit=limit, offset=offset)


@router.post("/sessions/{session_id}/knowledge-evolution")
async def run_knowledge_evolution(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_knowledge_evolution_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/dataset-evolution")
async def run_dataset_evolution(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_dataset_evolution_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/simulation")
async def run_evolution_simulation(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_evolution_simulation_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/recommendation")
async def generate_recommendation(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_recommendation_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review_evolution(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review_evolution(session_id, decision=payload.decision, admin_id=admin.admin.public_id)


# -- RAG Sandbox evaluation ------------------------------------------------------


@router.post("/sessions/{session_id}/rag-evaluation")
async def run_rag_evaluation(
    session_id: str, payload: RunRagEvaluationRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).run_rag_evaluation_stage(
        session_id, rag_sandbox_experiment_public_id=payload.rag_sandbox_experiment_public_id,
        retrieval_run_public_id=payload.retrieval_run_public_id,
        generation_assignment_public_id=payload.generation_assignment_public_id,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/rag-evaluation/finalize")
async def finalize_rag_evaluation(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).finalize_rag_evaluation_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/rag-review")
async def admin_review_rag(
    session_id: str, payload: RagAdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review_rag(session_id, decision=payload.decision, admin_id=admin.admin.public_id)
