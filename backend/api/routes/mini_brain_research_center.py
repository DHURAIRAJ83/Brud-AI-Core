"""MB-10: Brud Mini Brain AI Research & Knowledge Acquisition Center --
authenticated admin-only APIs. Independent prefix
(`/admin/mini-brain/research-center`), separate from every system this
phase reads from (MB-09 Planning Center, MB-05 Dataset Intelligence,
MB-06 Learning Supervisor, the duplicate-detection service, RAG
Sandbox). No route here writes a dataset record, approves a dataset,
starts training, deploys a model, activates a runtime, or modifies
MB-06/MB-07/MB-08/MB-09 -- every mutating route only ever writes to
MB-10's own tables (or, for the RAG Sandbox generation/evaluation
routes, to RAG Sandbox's own tables through its own existing service
methods, exactly as MB-06 already does).

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06/MB-08/MB-09, so every stage is
independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_research_center import (
    AddProviderRequest,
    AnalyzeTrainingReportRequest,
    BuildLocalDraftRequest,
    CreateSessionRequest,
    DraftAdminReviewRequest,
    IngestProviderResultsRequest,
    PrepareResearchRequestRequest,
    RagAdminReviewRequest,
    RecordMemoryRequest,
    RunRagEvaluationRequest,
    SelectModeRequest,
    SetProviderStatusRequest,
)
from backend.services.mini_brain_research_center_service import MiniBrainResearchCenterService

router = APIRouter(
    prefix="/admin/mini-brain/research-center",
    tags=["admin-mini-brain-research-center"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainResearchCenterService:
    return MiniBrainResearchCenterService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "ai_model_used": False,
        "external_providers_called": False,
        "writes_performed": True,
        "writes_scope": (
            "own tables only (mini_brain_research_provider_registry, mini_brain_research_memory, "
            "mini_brain_research_sessions/_events); RAG Sandbox generation/evaluation/report routes "
            "write to RAG Sandbox's own tables through its own existing service methods, exactly as MB-06 does"
        ),
        "pipeline_stages": [
            "research_request", "mode_selection", "local_draft", "provider_request",
            "provider_consensus", "dataset_draft", "awaiting_draft_review", "rag_evaluation",
            "awaiting_rag_review", "training_gate", "closed",
        ],
        "rag_first_policy": "every dataset draft must pass through RAG Sandbox before the training gate can open",
    }


# -- provider registry (real, admin-extensible) -------------------------------------


@router.get("/providers")
async def list_providers(settings: SettingsDependency, status: str | None = Query(default=None)):
    return service(settings).list_providers(status=status)


@router.post("/providers")
async def add_provider(payload: AddProviderRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).add_provider(
        provider_key=payload.provider_key, display_name=payload.display_name,
        requires_external_call=payload.requires_external_call, description=payload.description,
        admin_id=admin.admin.public_id,
    )


@router.post("/providers/{provider_key}/status")
async def set_provider_status(
    provider_key: str, payload: SetProviderStatusRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).set_provider_status(provider_key, status=payload.status, admin_id=admin.admin.public_id)


# -- research memory (permanent, always available) -----------------------------------


@router.post("/sessions/{session_id}/memory")
async def record_memory(
    session_id: str, payload: RecordMemoryRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).record_memory(session_id, notes=payload.notes, admin_id=admin.admin.public_id)


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


# -- research sessions ----------------------------------------------------------------


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


@router.post("/sessions/{session_id}/research-request")
async def prepare_research_request(
    session_id: str, payload: PrepareResearchRequestRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).prepare_research_request_stage(
        session_id, planning_center_session_public_id=payload.planning_center_session_public_id,
        priority=payload.priority, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/mode")
async def select_mode(
    session_id: str, payload: SelectModeRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).select_mode_stage(
        session_id, mode=payload.mode, requested_provider_keys=payload.requested_provider_keys or None,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/local-draft")
async def build_local_draft(
    session_id: str, payload: BuildLocalDraftRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).build_local_draft_stage(
        session_id, existing_dataset_source_public_id=payload.existing_dataset_source_public_id,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/provider-request")
async def prepare_provider_request_package(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).prepare_provider_request_package_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/provider-consensus")
async def ingest_provider_results(
    session_id: str, payload: IngestProviderResultsRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).ingest_provider_results_stage(
        session_id, provider_outputs=[o.model_dump() for o in payload.provider_outputs],
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/dataset-draft")
async def build_dataset_draft(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).build_dataset_draft_stage(session_id, admin_id=admin.admin.public_id)


@router.get("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency):
    return service(settings).generate_report(session_id)


@router.post("/sessions/{session_id}/draft-review")
async def admin_review_draft(
    session_id: str, payload: DraftAdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review_draft(session_id, decision=payload.decision, admin_id=admin.admin.public_id)


# -- RAG FIRST POLICY: RAG Sandbox evaluation ------------------------------------------


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


# -- training gate: eligibility check only, never a training trigger ------------------


@router.post("/sessions/{session_id}/training-gate")
async def check_training_gate(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).check_training_gate_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/training-report")
async def analyze_training_report(
    session_id: str, payload: AnalyzeTrainingReportRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).analyze_training_report(
        session_id, learning_supervisor_session_public_id=payload.learning_supervisor_session_public_id,
        admin_id=admin.admin.public_id,
    )
