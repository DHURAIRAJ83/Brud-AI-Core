"""MB-06: Brud Mini Brain Learning Supervisor -- authenticated
admin-only APIs. Independent prefix
(`/admin/mini-brain/learning-supervisor`), separate from every other
system this phase composes (Dataset Studio, MB-05/MB-05.1, the
Training Engine's own `/admin/pretraining` routes, Model Evaluation,
RAG Sandbox). No route here trains a model, writes a dataset/tokenizer/
RAG/checkpoint/Runtime row, or deploys/exports anything -- every
mutating route is a thin pass-through to
`MiniBrainLearningSupervisorService`, which itself only ever calls
other systems' already-existing public methods.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_learning_supervisor import (
    AdminReviewRequest,
    CompareModelsRequest,
    DatasetDecisionRequest,
    LearningSessionCreateRequest,
    RagDecisionRequest,
    ReleaseCandidateRequest,
    RunBenchmarkRequest,
    RunRagEvaluationRequest,
    SubmitTrainingRequestRequest,
)
from backend.services.mini_brain_learning_supervisor_service import (
    MiniBrainLearningSupervisorService,
)
from core_model.mini_brain.learning_supervisor.training_request_builder import (
    available_profiles as _available_profiles,
)

router = APIRouter(
    prefix="/admin/mini-brain/learning-supervisor",
    tags=["admin-mini-brain-learning-supervisor"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainLearningSupervisorService:
    return MiniBrainLearningSupervisorService(settings)


@router.get("/hyperparameter-profiles")
async def hyperparameter_profiles():
    return {"items": _available_profiles()}


@router.post("/sessions")
async def create_session(
    payload: LearningSessionCreateRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_session(
        dataset_source_public_id=payload.dataset_source_public_id,
        hyperparameter_profile=payload.hyperparameter_profile,
        admin_id=admin.admin.public_id,
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


@router.post("/sessions/{session_id}/validate-dataset")
async def validate_dataset(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).validate_dataset(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/decide-dataset")
async def decide_dataset(
    session_id: str, payload: DatasetDecisionRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).decide_dataset(
        session_id, decision=payload.decision, admin_id=admin.admin.public_id
    )


@router.post("/sessions/{session_id}/rag-evaluation")
async def run_rag_evaluation(
    session_id: str, payload: RunRagEvaluationRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).run_rag_evaluation(
        session_id,
        rag_sandbox_experiment_public_id=payload.rag_sandbox_experiment_public_id,
        retrieval_run_public_id=payload.retrieval_run_public_id,
        generation_assignment_public_id=payload.generation_assignment_public_id,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/rag-evaluation/finalize")
async def finalize_rag_evaluation(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).finalize_rag_evaluation(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/decide-rag")
async def decide_rag(
    session_id: str, payload: RagDecisionRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).decide_rag(
        session_id, decision=payload.decision, admin_id=admin.admin.public_id
    )


@router.post("/sessions/{session_id}/training-request")
async def submit_training_request(
    session_id: str, payload: SubmitTrainingRequestRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).submit_training_request(
        session_id,
        name=payload.name,
        dataset_version_public_id=payload.dataset_version_public_id,
        tokenizer_version_public_id=payload.tokenizer_version_public_id,
        core_model_version_public_id=payload.core_model_version_public_id,
        hyperparameter_profile=payload.hyperparameter_profile,
        admin_id=admin.admin.public_id,
    )


@router.get("/sessions/{session_id}/training-monitor")
async def monitor_training(session_id: str, settings: SettingsDependency):
    return service(settings).monitor_training(session_id)


@router.post("/sessions/{session_id}/analyze-training")
async def analyze_training_result(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze_training_result(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/benchmark")
async def run_benchmark(
    session_id: str, payload: RunBenchmarkRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).run_benchmark(
        session_id,
        model_evaluation_fixture_set_public_id=payload.model_evaluation_fixture_set_public_id,
        candidate_core_model_version_public_id=payload.candidate_core_model_version_public_id,
        generation_configuration=payload.generation_configuration,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/compare-models")
async def compare_models(
    session_id: str, payload: CompareModelsRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).compare_models(
        session_id,
        previous_benchmark_run_public_id=payload.previous_benchmark_run_public_id,
        admin_id=admin.admin.public_id,
    )


@router.post("/sessions/{session_id}/recommendations")
async def generate_recommendations(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_recommendations(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/admin-review")
async def admin_review(
    session_id: str, payload: AdminReviewRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).admin_review(
        session_id, decision=payload.decision, admin_id=admin.admin.public_id
    )


@router.post("/sessions/{session_id}/release-candidate")
async def create_release_candidate(
    session_id: str, payload: ReleaseCandidateRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_release_candidate(
        session_id,
        checkpoint_public_id=payload.checkpoint_public_id,
        admin_id=admin.admin.public_id,
        override_comment=payload.override_comment,
    )
