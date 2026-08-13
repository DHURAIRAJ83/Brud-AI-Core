"""MB-23: Public Chat Runtime -- fully public (no admin auth, no CSRF,
matching Phase 18's own `/api/chat` convention: "no Admin
authentication requirement for normal public chat"). Every route is
rate-limited using the exact same `check_rate_limit()` Phase 18's own
`/api/chat` route already uses. `send_message` never duplicates model/
RAG/vision/tool logic -- it calls `MiniBrainPublicChatRuntimeService.
send_message()`, which itself calls the existing
`PublicChatRoutingService.handle_message()` exactly once.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.dependencies import SettingsDependency
from backend.core.exceptions import BrudError
from backend.models.mini_brain_public_chat_runtime import (
    SendMessageRequest,
    StartSessionRequest,
    SubmitFeedbackRequest,
)
from backend.services.public_chat_rate_limiter import check_rate_limit
from backend.services.mini_brain_public_chat_runtime_service import MiniBrainPublicChatRuntimeService

router = APIRouter(prefix="/public/chat", tags=["public-chat-runtime"])


class PublicChatRuntimeRateLimited(BrudError):
    status_code = 429
    code = "PUBLIC_CHAT_RUNTIME_RATE_LIMITED"

    def __init__(self) -> None:
        super().__init__("Too many requests. Please wait a moment and try again.")


def _client_key(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


def _service(settings) -> MiniBrainPublicChatRuntimeService:
    return MiniBrainPublicChatRuntimeService(settings)


def _enforce_rate_limit(request: Request, settings) -> None:
    allowed = check_rate_limit(
        _client_key(request), max_requests=settings.public_chat_rate_limit_max_requests,
        window_seconds=settings.public_chat_rate_limit_window_seconds,
    )
    if not allowed:
        raise PublicChatRuntimeRateLimited()


@router.post("/sessions")
async def start_session(request: Request, payload: StartSessionRequest, settings: SettingsDependency):
    _enforce_rate_limit(request, settings)
    return _service(settings).start_session(raw_client_key=_client_key(request), language=payload.language)


@router.post("/sessions/{session_id}/messages")
async def send_message(session_id: str, request: Request, payload: SendMessageRequest, settings: SettingsDependency):
    _enforce_rate_limit(request, settings)
    return _service(settings).send_message(session_id, raw_message=payload.message)


@router.post("/sessions/{session_id}/feedback")
async def submit_feedback(session_id: str, request: Request, payload: SubmitFeedbackRequest, settings: SettingsDependency):
    _enforce_rate_limit(request, settings)
    return _service(settings).submit_feedback(
        session_id, satisfaction_rating=payload.satisfaction_rating, raw_comment=payload.comment,
    )


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str, request: Request, settings: SettingsDependency):
    _enforce_rate_limit(request, settings)
    return _service(settings).end_session(session_id)


__all__ = ["router"]
