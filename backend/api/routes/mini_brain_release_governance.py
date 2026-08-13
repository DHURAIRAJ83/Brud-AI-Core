"""MB-20: Brud Mini Brain Release Readiness & Deployment Governance
Center -- authenticated admin-only APIs. Independent prefix (`/admin/
mini-brain/release-governance`), separate from every system this phase
reads from (MB-16 Multimodal Dataset Generator, MB-17 Vision RAG,
MB-18 Training Pipeline, MB-19 Evaluation Center). No route here
deploys a model, starts an inference server or public chat, calls a
runtime-manager start API, calls a Docker/Kubernetes deployment API,
uploads weights anywhere, exports GGUF, quantizes, or enables
production traffic -- every mutating route only ever writes to MB-20's
own tables and its own release directory. Approval never implies
production safety.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06 through MB-19, so every stage is
independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_release_governance import (
    AdminReviewRequest,
    CollectDatasetsRequest,
    CollectEvaluationRequest,
    CollectRagRequest,
    CollectTrainingPackageRequest,
    CreateSessionRequest,
)
from backend.services.mini_brain_release_governance_service import MiniBrainReleaseGovernanceService

router = APIRouter(
    prefix="/admin/mini-brain/release-governance",
    tags=["admin-mini-brain-release-governance"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainReleaseGovernanceService:
    return MiniBrainReleaseGovernanceService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "model_deployed": False,
        "inference_server_started": False,
        "public_chat_started": False,
        "runtime_manager_start_called": False,
        "docker_or_kubernetes_api_called": False,
        "weights_uploaded": False,
        "gguf_exported": False,
        "quantization_performed": False,
        "model_weights_modified": False,
        "mb16_writes_performed": False,
        "mb17_writes_performed": False,
        "mb18_writes_performed": False,
        "mb19_writes_performed": False,
        "models_downloaded": False,
        "external_ai_providers_called": False,
        "production_traffic_enabled": False,
        "requires_certified_sources": True,
        "automatic_approval": False,
        "writes_scope": (
            "own tables only (mini_brain_release_governance_sessions/_events/_memory, "
            "mini_brain_release_governance_artifacts) plus its own release directory on disk"
        ),
        "pipeline_stages": [
            "collect_datasets", "collect_rag", "collect_training_package", "collect_evaluation",
            "run_safety_gates", "run_compliance_gates", "run_benchmark_gates", "build_risk_rollback",
            "build_release_package", "generate_report", "awaiting_admin_review", "closed",
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


@router.get("/sessions/{session_id}/artifacts")
async def list_artifacts(session_id: str, settings: SettingsDependency):
    return service(settings).list_artifacts(session_id)


@router.get("/artifacts/{artifact_id}")
async def get_artifact_metadata(artifact_id: str, settings: SettingsDependency):
    return service(settings).get_artifact_metadata(artifact_id)


@router.get("/memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


# -- stages --------------------------------------------------------------------


@router.post("/sessions/{session_id}/collect-datasets")
async def run_collect_datasets(
    session_id: str, payload: CollectDatasetsRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_collect_datasets_stage(
        session_id, dataset_session_public_ids=payload.dataset_session_public_ids,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/collect-rag")
async def run_collect_rag(
    session_id: str, payload: CollectRagRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_collect_rag_stage(
        session_id, rag_session_public_ids=payload.rag_session_public_ids, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/collect-package")
async def run_collect_training_package(
    session_id: str, payload: CollectTrainingPackageRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_collect_training_package_stage(
        session_id, training_package_session_public_id=payload.training_package_session_public_id,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/collect-evaluation")
async def run_collect_evaluation(
    session_id: str, payload: CollectEvaluationRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_collect_evaluation_stage(
        session_id, evaluation_session_public_id=payload.evaluation_session_public_id,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/run-safety")
async def run_safety(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_safety_gates_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/run-compliance")
async def run_compliance(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_compliance_gates_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/run-benchmarks")
async def run_benchmarks(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_benchmark_gates_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/build-risk-rollback")
async def build_risk_rollback(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_build_risk_rollback_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/build-package")
async def build_package(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_build_release_package_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).admin_review(session_id, decision=payload.decision, admin_id=admin.admin.public_id)
