"""MB-09: Brud Mini Brain Continuous Learning Center -- authenticated
admin-only APIs. Independent prefix
(`/admin/mini-brain/continuous-learning-center`), separate from every
system this phase reads from (MB-08, MB-05 Dataset Intelligence, the
duplicate-detection service). No route here edits Dataset Studio,
modifies the Training Engine, MB-06, MB-07, or Runtime, creates a RAG
dataset, launches training, or deploys/activates a model -- every
mutating route only ever writes to MB-09's own tables.

Each planning stage gets its own independently-callable route, mirroring
the precedent set by MB-06/MB-07/MB-08, so every stage is independently
testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_continuous_learning_center import (
    AdminReviewRequest,
    BuildDraftRequest,
    IngestProviderResultsRequest,
    PlanDatasetEvolutionRequest,
    PrepareProviderRequestRequest,
    RecordMemoryRequest,
)
from backend.services.mini_brain_continuous_learning_center_service import (
    MiniBrainContinuousLearningCenterService,
)

router = APIRouter(
    prefix="/admin/mini-brain/continuous-learning-center",
    tags=["admin-mini-brain-continuous-learning-center"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainContinuousLearningCenterService:
    return MiniBrainContinuousLearningCenterService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "ai_model_used": False,
        "external_providers_called": False,
        "writes_performed": True,
        "writes_scope": "own tables only (mini_brain_learning_memory, mini_brain_continuous_learning_center_sessions/_events)",
        "pipeline_stages": [
            "knowledge_gap_evolution", "learning_queue", "draft_planning", "provider_request",
            "provider_consensus", "dataset_evolution", "knowledge_roadmap", "recommendation",
            "awaiting_admin_review",
        ],
    }


# -- learning memory (permanent, always available) ---------------------------------


@router.post("/memory")
async def record_memory(
    payload: RecordMemoryRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).record_memory(
        continuous_learning_session_public_id=payload.continuous_learning_session_public_id,
        model_version_public_id=payload.model_version_public_id,
        dataset_version_public_id=payload.dataset_version_public_id,
        benchmark_summary=payload.benchmark_summary, admin_decision=payload.admin_decision,
        improvement_notes=payload.improvement_notes, admin_id=admin.admin.public_id,
    )


@router.get("/memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


@router.get("/memory/{memory_id}")
async def get_memory(memory_id: str, settings: SettingsDependency):
    return service(settings).get_memory(memory_id)


# -- planning sessions ---------------------------------------------------------------


@router.post("/sessions")
async def create_session(settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_session(admin_id=admin.admin.public_id)


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


@router.post("/sessions/{session_id}/knowledge-gap-evolution")
async def evolve_knowledge_gaps(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).evolve_knowledge_gaps_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/learning-queue")
async def build_learning_queue(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).build_learning_queue_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/draft")
async def build_draft(
    session_id: str, payload: BuildDraftRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).build_draft_stage(
        session_id, topic=payload.topic, admin_id=admin.admin.public_id
    )


@router.post("/sessions/{session_id}/provider-request")
async def prepare_provider_request(
    session_id: str, payload: PrepareProviderRequestRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).prepare_provider_request_stage(
        session_id, requested_providers=payload.requested_providers, admin_id=admin.admin.public_id
    )


@router.post("/sessions/{session_id}/provider-consensus")
async def ingest_provider_results(
    session_id: str, payload: IngestProviderResultsRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).ingest_provider_results_stage(
        session_id,
        provider_outputs=[o.model_dump() for o in payload.provider_outputs],
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/dataset-evolution")
async def plan_dataset_evolution(
    session_id: str, payload: PlanDatasetEvolutionRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).plan_dataset_evolution_stage(
        session_id, existing_dataset_source_public_id=payload.existing_dataset_source_public_id,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/roadmap")
async def build_roadmap(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).build_roadmap_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/recommendation")
async def generate_recommendation(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_recommendation_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review(
        session_id, decision=payload.decision, admin_id=admin.admin.public_id
    )
