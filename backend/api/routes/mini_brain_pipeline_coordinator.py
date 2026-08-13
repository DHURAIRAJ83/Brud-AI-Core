"""MB-12: Brud Mini Brain Autonomous AI Knowledge Pipeline Coordinator
-- authenticated admin-only APIs. Independent prefix
(`/admin/mini-brain/pipeline-coordinator`), separate from every system
this phase reads from (MB-05, MB-05.1, MB-06, MB-08, MB-09, MB-10,
MB-11). No route here writes a dataset record, starts training,
deploys a model, or modifies RAG -- every mutating route only ever
writes to MB-12's own tables.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06/MB-09/MB-10/MB-11, so every stage
is independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_pipeline_coordinator import (
    AdminDecisionRequest,
    CreateSessionRequest,
    LinkDatasetEvolutionRequest,
    LinkResearchCenterRequest,
    LinkResearchRequest,
    LinkTrainingRequest,
)
from backend.services.mini_brain_pipeline_coordinator_service import (
    MiniBrainPipelineCoordinatorService,
)

router = APIRouter(
    prefix="/admin/mini-brain/pipeline-coordinator",
    tags=["admin-mini-brain-pipeline-coordinator"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainPipelineCoordinatorService:
    return MiniBrainPipelineCoordinatorService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "ai_model_used": False,
        "training_started": False,
        "models_deployed": False,
        "dataset_writes_performed": False,
        "rag_sandbox_called_directly": False,
        "writes_scope": "own tables only (mini_brain_pipeline_sessions/_events)",
        "pipeline_stages": [
            "new", "under_research", "provider_consensus_pending", "draft_ready", "dataset_planned",
            "rag_testing", "training_candidate", "training_running", "benchmark_ready",
            "release_candidate", "completed", "archived",
        ],
    }


# -- sessions ----------------------------------------------------------------


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_session(topic=payload.topic, admin_id=admin.admin.public_id)


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


@router.post("/sessions/{session_id}/link-research")
async def link_research(
    session_id: str, payload: LinkResearchRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).link_research_stage(
        session_id, mb09_session_public_id=payload.mb09_session_public_id, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/link-research-center")
async def link_research_center(
    session_id: str, payload: LinkResearchCenterRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).link_research_center_stage(
        session_id, mb10_session_public_id=payload.mb10_session_public_id, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/refresh-research-center")
async def refresh_research_center(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).refresh_research_center_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/link-dataset-evolution")
async def link_dataset_evolution(
    session_id: str, payload: LinkDatasetEvolutionRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).link_dataset_evolution_stage(
        session_id, mb11_session_public_id=payload.mb11_session_public_id, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/rag-first-enforcement")
async def run_rag_first_enforcement(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_rag_first_enforcement(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/link-training")
async def link_training(
    session_id: str, payload: LinkTrainingRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).link_training_stage(
        session_id, mb06_session_public_id=payload.mb06_session_public_id, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/refresh-training")
async def refresh_training(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).refresh_training_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/training-readiness")
async def generate_training_readiness_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_training_readiness_report(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/timeline")
async def generate_timeline(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_timeline(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/improvement-prediction")
async def predict_improvement(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).predict_improvement_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/recommendation")
async def generate_recommendation(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_recommendation(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_master_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_master_report(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-decision")
async def admin_decide(
    session_id: str, payload: AdminDecisionRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_decide(session_id, decision=payload.decision, admin_id=admin.admin.public_id)
