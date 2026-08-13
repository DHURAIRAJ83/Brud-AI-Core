"""MB-08: Brud Mini Brain Continuous Learning & Feedback Engine --
authenticated admin-only APIs. Independent prefix
(`/admin/mini-brain/continuous-learning`), separate from every system
this phase reads from (Public Chat routing/feedback, the Knowledge Gap
Registry, MB-05/MB-05.1). No route here retrains a model, edits a
dataset, modifies a checkpoint, or activates a model -- every mutating
route only ever writes to MB-08's own two tables.

Each of the 10 workflow stages gets its own independently-callable
route (more granular than the task spec's shorthand 10-endpoint list)
so every stage is independently testable, matching the spec's own
explicit testing requirement and the same precedent set by MB-06/MB-07.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_continuous_learning import (
    AdminReviewRequest,
    ContinuousLearningSessionCreateRequest,
)
from backend.services.mini_brain_continuous_learning_service import (
    MiniBrainContinuousLearningService,
)

router = APIRouter(
    prefix="/admin/mini-brain/continuous-learning",
    tags=["admin-mini-brain-continuous-learning"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainContinuousLearningService:
    return MiniBrainContinuousLearningService(settings)


@router.get("/diagnostics")
async def diagnostics():
    return {
        "ai_model_used": False,
        "writes_performed": True,
        "writes_scope": "own tables only (mini_brain_continuous_learning_sessions/_events)",
        "pipeline_stages": [
            "feedback_collection", "failure_analysis", "hallucination_analysis",
            "knowledge_gap_analysis", "weak_topic_detection", "difficulty_analysis",
            "dataset_recommendation", "training_recommendation", "priority_ranking",
            "awaiting_admin_review",
        ],
    }


@router.post("/sessions")
async def create_session(
    payload: ContinuousLearningSessionCreateRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return service(settings).create_session(
        cycle_window_days=payload.cycle_window_days, admin_id=admin.admin.public_id
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


@router.post("/sessions/{session_id}/feedback")
async def collect_feedback(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).collect_feedback_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/failures")
async def analyze_failures(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze_failures_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/hallucinations")
async def analyze_hallucinations(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze_hallucinations_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/knowledge-gaps")
async def analyze_knowledge_gaps(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze_knowledge_gaps_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/topics")
async def detect_weak_topics(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).detect_weak_topics_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/difficulty")
async def analyze_difficulty(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).analyze_difficulty_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/datasets")
async def recommend_datasets(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).recommend_datasets_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/training")
async def recommend_training(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).recommend_training_stage(session_id, admin_id=admin.admin.public_id)


@router.post("/sessions/{session_id}/priority")
async def rank_priorities(session_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).rank_priorities_stage(session_id, admin_id=admin.admin.public_id)


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
