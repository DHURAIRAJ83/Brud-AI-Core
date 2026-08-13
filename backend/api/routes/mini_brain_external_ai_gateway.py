"""MB-21: Brud Mini Brain External AI Evaluation Gateway --
authenticated admin-only APIs. Independent prefix (`/admin/mini-brain/
external-ai-gateway`). External AI providers are used strictly as
evaluation assistants, never as autonomous decision-makers. No route
here trains a model, modifies weights, starts a runtime, deploys,
approves a dataset, approves a release, writes into Dataset Studio or
Document Workspace, executes a shell command, or dispatches a provider
request before an explicit admin authorization is recorded on this
exact session -- every mutating route only ever writes to MB-21's own
tables. Every provider output remains untrusted candidate evidence.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06 through MB-20, so every stage is
independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_external_ai_gateway import (
    AdminReviewRequest,
    AuthorizeRequest,
    CreateSessionRequest,
    DispatchRequest,
    SanitizeRequest,
    SelectProvidersRequest,
)
from backend.services.mini_brain_external_ai_gateway_service import MiniBrainExternalAiGatewayService

router = APIRouter(
    prefix="/admin/mini-brain/external-ai-gateway",
    tags=["admin-mini-brain-external-ai-gateway"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainExternalAiGatewayService:
    return MiniBrainExternalAiGatewayService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "training_started": False,
        "model_weights_modified": False,
        "runtime_started": False,
        "model_deployed": False,
        "dataset_approved": False,
        "release_approved": False,
        "dataset_studio_writes_performed": False,
        "document_workspace_writes_performed": False,
        "mb13_writes_performed": False,
        "mb16_writes_performed": False,
        "mb17_writes_performed": False,
        "mb18_writes_performed": False,
        "mb19_writes_performed": False,
        "mb20_writes_performed": False,
        "shell_commands_executed": False,
        "executable_files_downloaded": False,
        "provider_calls_require_authorization": True,
        "automatic_approval": False,
        "external_ai_output_treated_as": "untrusted candidate evidence only",
        "writes_scope": (
            "own tables only (mini_brain_external_ai_sessions/_events/_memory, "
            "mini_brain_external_ai_provider_runs)"
        ),
        "pipeline_stages": [
            "validate_authorization", "sanitize_inputs", "select_providers", "dispatch_requests",
            "collect_responses", "normalize_responses", "analyze_agreement", "build_evidence",
            "generate_report", "awaiting_admin_review", "reviewed", "archived",
        ],
    }


# -- sessions ----------------------------------------------------------------


@router.post("/sessions")
async def create_session(payload: CreateSessionRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).create_session(
        topic=payload.topic, purpose=payload.purpose, admin_id=admin.admin.public_id,
        dataset_session_public_ids=payload.dataset_session_public_ids,
        rag_session_public_id=payload.rag_session_public_id,
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


@router.get("/sessions/{session_id}/provider-runs")
async def list_provider_runs(session_id: str, settings: SettingsDependency):
    return service(settings).list_provider_runs(session_id)


@router.get("/memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


# -- stages --------------------------------------------------------------------


@router.post("/sessions/{session_id}/authorize")
async def authorize(
    session_id: str, payload: AuthorizeRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_validate_authorization_stage(
        session_id, authorization_note=payload.authorization_note, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/sanitize")
async def sanitize(
    session_id: str, payload: SanitizeRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_sanitize_inputs_stage(
        session_id, admin_stated_need=payload.admin_stated_need, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/select-providers")
async def select_providers(
    session_id: str, payload: SelectProvidersRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_select_providers_stage(
        session_id, requested_provider_keys=payload.requested_provider_keys, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/dispatch")
async def dispatch(
    session_id: str, payload: DispatchRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_dispatch_requests_stage(
        session_id, admin_id=admin.admin.public_id, timeout_seconds=payload.timeout_seconds,
        retain_raw_responses=payload.retain_raw_responses,
    )


@router.post("/sessions/{session_id}/collect")
async def collect(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_collect_responses_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/normalize")
async def normalize(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_normalize_responses_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/analyze")
async def analyze(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_analyze_agreement_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/build-evidence")
async def build_evidence(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_build_evidence_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).admin_review(session_id, decision=payload.decision, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/archive")
async def archive(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).archive(session_id, admin_id=admin.admin.public_id)
