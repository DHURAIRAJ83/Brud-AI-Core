"""MB-19: Brud Mini Brain Evaluation & Benchmark Center --
authenticated admin-only APIs. Independent prefix (`/admin/mini-brain/
evaluation-center`), separate from every system this phase reads from
(MB-16 Multimodal Dataset Generator, MB-17 Vision RAG, MB-18 Training
Pipeline). No route here starts a training job, fine-tunes, exports
GGUF, quantizes, deploys, or activates a runtime -- every mutating
route only ever writes to MB-19's own tables and its own export
directory. Evaluation approval never guarantees production model
quality.

Each workflow stage gets its own independently-callable route,
mirroring the precedent set by MB-06 through MB-18, so every stage is
independently testable.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_evaluation_center import (
    AdminReviewRequest,
    CollectDatasetsRequest,
    CollectRagSessionsRequest,
    CollectTrainingPackagesRequest,
    CreateSessionRequest,
    RegressionComparisonRequest,
)
from backend.services.mini_brain_evaluation_center_service import MiniBrainEvaluationCenterService

router = APIRouter(
    prefix="/admin/mini-brain/evaluation-center",
    tags=["admin-mini-brain-evaluation-center"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainEvaluationCenterService:
    return MiniBrainEvaluationCenterService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "training_started": False,
        "fine_tuning_performed": False,
        "gguf_export_performed": False,
        "quantization_performed": False,
        "runtime_activated": False,
        "models_deployed": False,
        "mb16_writes_performed": False,
        "mb17_writes_performed": False,
        "mb18_writes_performed": False,
        "document_workspace_writes_performed": False,
        "external_ai_providers_called": False,
        "models_downloaded_automatically": False,
        "model_inference_performed": False,
        "requires_certified_dataset": True,
        "automatic_approval": False,
        "writes_scope": (
            "own tables only (mini_brain_evaluation_sessions/_events/_memory, "
            "mini_brain_benchmark_results) plus its own export directory on disk"
        ),
        "pipeline_stages": [
            "collect_datasets", "collect_rag_sessions", "collect_training_packages",
            "run_language_benchmarks", "run_ocr_benchmarks", "run_grounding_retrieval_benchmarks",
            "run_multimodal_benchmarks", "run_package_benchmarks", "run_regression_comparison",
            "generate_report", "awaiting_admin_review", "closed",
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


@router.get("/sessions/{session_id}/results")
async def list_benchmark_results(session_id: str, settings: SettingsDependency, category: str | None = None):
    return service(settings).list_results(session_id, category=category)


@router.get("/sessions/{session_id}/exports")
async def list_exports(session_id: str, settings: SettingsDependency):
    session_data = service(settings).session(session_id)
    return {"items": session_data.get("export_manifest", {}).get("artifacts", [])}


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


@router.post("/sessions/{session_id}/collect-rag-sessions")
async def run_collect_rag_sessions(
    session_id: str, payload: CollectRagSessionsRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_collect_rag_sessions_stage(
        session_id, rag_session_public_ids=payload.rag_session_public_ids, admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/collect-training-packages")
async def run_collect_training_packages(
    session_id: str, payload: CollectTrainingPackagesRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_collect_training_packages_stage(
        session_id, training_package_session_public_ids=payload.training_package_session_public_ids,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/language-benchmarks")
async def run_language_benchmarks(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_language_benchmarks_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/ocr-benchmarks")
async def run_ocr_benchmarks(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_ocr_benchmarks_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/grounding-retrieval-benchmarks")
async def run_grounding_retrieval_benchmarks(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_grounding_retrieval_benchmarks_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/multimodal-benchmarks")
async def run_multimodal_benchmarks(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_multimodal_benchmarks_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/package-benchmarks")
async def run_package_benchmarks(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_package_benchmarks_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/regression")
async def run_regression(
    session_id: str, payload: RegressionComparisonRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).run_regression_comparison_stage(
        session_id, admin_id=admin.admin.public_id, baseline_session_public_id=payload.baseline_session_public_id,
    )


@router.post("/sessions/{session_id}/report")
async def generate_report(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_report_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).admin_review(session_id, decision=payload.decision, admin_id=admin.admin.public_id)


@router.post("/auto-evaluate")
async def auto_evaluate_candidate(
    settings: SettingsDependency,
    admin: CsrfDependency,
    run_id: str = "run-default",
    model_version: str = "candidate-v1",
    dataset_version: str = "dataset-v1",
):
    """Executes automated 17-category post-training evaluation suite and regression analysis."""
    from backend.services.automated_model_evaluation_service import (
        AutomatedModelEvaluationService,
    )

    eval_service = AutomatedModelEvaluationService(settings)
    report = eval_service.run_post_training_evaluation(
        run_id=run_id,
        model_version=model_version,
        dataset_version=dataset_version,
        admin_id=admin.admin.public_id,
    )
    from dataclasses import asdict

    return asdict(report)

