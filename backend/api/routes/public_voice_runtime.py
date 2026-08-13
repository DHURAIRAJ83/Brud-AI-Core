"""MB-26: Voice & Speech Runtime -- fully public routes (no admin
auth, no CSRF, matching MB-23's own `/api/public/chat` convention).
Every route is rate-limited using the exact same `check_rate_limit()`
MB-23's own public chat runtime routes already use.

`session_mode` is always forced to `'public_chat'` here server-side --
a public caller can never request `'admin_assistant'` mode through
this router. Session ownership (for `GET`/`chunks`/`finish`/`close`)
is verified via the same client-key hash MB-23 already uses; a
mismatch or missing session returns 404, never 403, so an unauthorized
caller cannot even confirm a given session id exists.
"""

from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Request

from backend.api.dependencies import SettingsDependency
from backend.core.exceptions import BrudError
from backend.database.repositories.base import NotFoundError
from backend.models.mini_brain_voice_runtime import (
    CreateVoiceSessionRequest,
    FinishVoiceSessionRequest,
    VoiceChunkRequest,
)
from backend.services.mini_brain_voice_runtime_service import MiniBrainVoiceRuntimeService
from backend.services.public_chat_rate_limiter import check_rate_limit

router = APIRouter(prefix="/public/voice", tags=["public-voice-runtime"])


class VoiceRuntimeRateLimited(BrudError):
    status_code = 429
    code = "VOICE_RUNTIME_RATE_LIMITED"

    def __init__(self) -> None:
        super().__init__("Too many requests. Please wait a moment and try again.")


class VoiceAudioDecodeError(BrudError):
    status_code = 422
    code = "VOICE_AUDIO_DECODE_ERROR"

    def __init__(self) -> None:
        super().__init__("audio_base64 could not be decoded.")


def _client_key(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


def _service(settings) -> MiniBrainVoiceRuntimeService:
    return MiniBrainVoiceRuntimeService(settings)


def _enforce_rate_limit(request: Request, settings) -> None:
    allowed = check_rate_limit(
        _client_key(request), max_requests=settings.public_chat_rate_limit_max_requests,
        window_seconds=settings.public_chat_rate_limit_window_seconds,
    )
    if not allowed:
        raise VoiceRuntimeRateLimited()


def _decode_audio(audio_base64: str) -> bytes:
    try:
        return base64.b64decode(audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VoiceAudioDecodeError() from exc


def _require_ownership(service: MiniBrainVoiceRuntimeService, session_id: str, request: Request) -> None:
    if not service.verify_ownership(session_id, raw_client_key=_client_key(request)):
        raise NotFoundError(f"voice session not found: {session_id}")


@router.post("/sessions")
async def create_session(request: Request, payload: CreateVoiceSessionRequest, settings: SettingsDependency):
    _enforce_rate_limit(request, settings)
    service = _service(settings)
    session = service.create_voice_session(
        session_mode="public_chat", conversation_id=payload.conversation_id,
        raw_client_key=_client_key(request),
    )
    permission = service.run_check_microphone_permission_stage(
        session["public_id"], explicit_consent_given=payload.explicit_consent,
    )
    if permission["status"] != "active":
        return permission
    return service.run_validate_scopes_stage(session["public_id"])


@router.post("/sessions/{session_id}/chunks")
async def send_chunk(session_id: str, request: Request, payload: VoiceChunkRequest, settings: SettingsDependency):
    _enforce_rate_limit(request, settings)
    service = _service(settings)
    _require_ownership(service, session_id, request)
    session_data = service.session(session_id)
    if session_data["stage"] == "scopes_validated":
        service.run_start_capture_stage(session_id)
    audio_bytes = _decode_audio(payload.audio_base64)
    return service.run_accept_audio_chunk_stage(session_id, sequence=payload.sequence, audio_bytes=audio_bytes)


@router.post("/sessions/{session_id}/finish")
async def finish_session(
    session_id: str, request: Request, settings: SettingsDependency,
    payload: FinishVoiceSessionRequest | None = None,
):
    _enforce_rate_limit(request, settings)
    service = _service(settings)
    _require_ownership(service, session_id, request)
    service.finish_voice_session(session_id)
    return service.session_response_payload(session_id)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request, settings: SettingsDependency):
    _enforce_rate_limit(request, settings)
    service = _service(settings)
    _require_ownership(service, session_id, request)
    return service.session_response_payload(session_id)


@router.post("/sessions/{session_id}/close")
async def close_session(session_id: str, request: Request, settings: SettingsDependency):
    _enforce_rate_limit(request, settings)
    service = _service(settings)
    _require_ownership(service, session_id, request)
    return service.close_voice_session(session_id)


__all__ = ["router"]
