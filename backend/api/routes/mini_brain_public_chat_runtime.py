"""MB-23: Brud Mini Brain Public Chat Runtime & Self-Improvement
Feedback Loop -- admin-only read/review APIs. Independent prefix
(`/admin/mini-brain/public-chat`), separate from the fully public
`/api/public/chat` routes. No route here approves an MB-16 dataset, an
MB-17 grounded answer, an MB-18 package, an MB-19 evaluation, or an
MB-20 release; no route dispatches an MB-21 provider; no route starts
or finalizes an MB-22 training job. `review_candidate` is the only
route that can move a candidate out of `pending_admin_review`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_public_chat_runtime import GenerateCandidatesRequest, ReviewCandidateRequest
from backend.services.mini_brain_public_chat_runtime_service import MiniBrainPublicChatRuntimeService

router = APIRouter(
    prefix="/admin/mini-brain/public-chat",
    tags=["admin-mini-brain-public-chat"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainPublicChatRuntimeService:
    return MiniBrainPublicChatRuntimeService(settings)


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()


# -- sessions ------------------------------------------------------------------


@router.get("/sessions")
async def list_sessions(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
):
    return service(settings).list_sessions(limit=limit, offset=offset, status=status)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, settings: SettingsDependency):
    return service(settings).session(session_id)


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: str, settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).messages(session_id, limit=limit, offset=offset)


@router.get("/sessions/{session_id}/signals")
async def list_signals(
    session_id: str, settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).signals(session_id, limit=limit, offset=offset)


@router.get("/sessions/{session_id}/events")
async def list_session_events(
    session_id: str, settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).events(session_public_id=session_id, limit=limit, offset=offset)


# -- clusters & candidates ------------------------------------------------------------


@router.get("/clusters")
async def list_clusters(settings: SettingsDependency, signal_limit: int = Query(default=100, ge=1, le=100)):
    return service(settings).list_clusters(signal_limit=signal_limit)


@router.post("/candidates/generate")
async def generate_candidates(payload: GenerateCandidatesRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_generate_candidates(
        admin_id=admin.admin.public_id, minimum_frequency=payload.minimum_frequency,
    )


@router.get("/candidates")
async def list_candidates(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None),
):
    return service(settings).list_candidates(status=status, limit=limit, offset=offset)


@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str, settings: SettingsDependency):
    return service(settings).candidate(candidate_id)


@router.get("/candidates/{candidate_id}/events")
async def list_candidate_events(
    candidate_id: str, settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).events(candidate_public_id=candidate_id, limit=limit, offset=offset)


@router.post("/candidates/{candidate_id}/review")
async def review_candidate(
    candidate_id: str, payload: ReviewCandidateRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).review_candidate(
        candidate_id, admin_id=admin.admin.public_id, decision=payload.decision, notes=payload.notes,
    )


# -- analytics & exports ------------------------------------------------------------------


@router.get("/analytics")
async def analytics(settings: SettingsDependency):
    return service(settings).analytics()


@router.get("/exports/analytics")
async def export_analytics(settings: SettingsDependency):
    return service(settings).export_analytics()


@router.get("/exports/candidates")
async def export_candidates(settings: SettingsDependency, status: str | None = Query(default=None)):
    return service(settings).export_candidates(status=status)


__all__ = ["router"]
