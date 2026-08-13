"""MB-26: Brud Mini Brain Voice & Speech Runtime -- admin-only APIs.
Independent prefix (`/admin/mini-brain/voice`). `test-stt`/`test-tts`
exercise a backend directly against a piece of admin-supplied
audio/text with no session record created -- for diagnostics and
manual verification only, never a shortcut into the 12-stage workflow.
"""

from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.exceptions import BrudError
from backend.models.mini_brain_voice_runtime import (
    CreateVoiceSessionRequest,
    TestSttRequest,
    TestTtsRequest,
)
from backend.services.mini_brain_voice_runtime_service import MiniBrainVoiceRuntimeService
from core_model.mini_brain.voice_runtime import (
    coqui_tts_backend,
    faster_whisper_backend,
    mock_speech_backend,
    mock_tts_backend,
)

router = APIRouter(
    prefix="/admin/mini-brain/voice",
    tags=["admin-mini-brain-voice-runtime"],
    dependencies=[Depends(require_admin)],
)


class VoiceAudioDecodeError(BrudError):
    status_code = 422
    code = "VOICE_AUDIO_DECODE_ERROR"

    def __init__(self) -> None:
        super().__init__("audio_base64 could not be decoded.")


def service(settings) -> MiniBrainVoiceRuntimeService:
    return MiniBrainVoiceRuntimeService(settings)


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()


@router.get("/sessions")
async def list_sessions(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None), session_mode: str | None = Query(default=None),
):
    return service(settings).list_sessions(limit=limit, offset=offset, status=status, session_mode=session_mode)


@router.get("/sessions/{session_id}")
async def session_detail(session_id: str, settings: SettingsDependency):
    return service(settings).session_response_payload(session_id)


@router.get("/events")
async def list_events(
    settings: SettingsDependency,
    limit: int = Query(default=100, ge=1, le=100), offset: int = Query(default=0, ge=0),
    session_id: str | None = Query(default=None),
):
    return service(settings).list_events(session_id, limit=limit, offset=offset)


@router.get("/memory")
async def list_memory(
    settings: SettingsDependency,
    limit: int = Query(default=50, ge=1, le=100), offset: int = Query(default=0, ge=0),
):
    return service(settings).list_memory(limit=limit, offset=offset)


@router.get("/statistics")
async def statistics(settings: SettingsDependency):
    return service(settings).statistics()


@router.post("/sessions")
async def create_admin_session(
    payload: CreateVoiceSessionRequest, settings: SettingsDependency, admin: CsrfDependency,
):
    svc = service(settings)
    session = svc.create_voice_session(
        session_mode="admin_assistant", conversation_id=payload.conversation_id,
        requester_admin_public_id=admin.admin.public_id,
    )
    permission = svc.run_check_microphone_permission_stage(session["public_id"], admin_authorized=True)
    if permission["status"] != "active":
        return permission
    return svc.run_validate_scopes_stage(session["public_id"])


@router.post("/test-stt")
async def test_stt(payload: TestSttRequest, settings: SettingsDependency, admin: CsrfDependency):
    try:
        audio_bytes = base64.b64decode(payload.audio_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise VoiceAudioDecodeError() from exc

    if faster_whisper_backend.is_available():
        return faster_whisper_backend.transcribe(
            audio_bytes=audio_bytes, model_size=settings.voice_stt_model_size,
        )
    return mock_speech_backend.transcribe(audio_bytes=audio_bytes)


@router.post("/test-tts")
async def test_tts(payload: TestTtsRequest, settings: SettingsDependency, admin: CsrfDependency):
    if coqui_tts_backend.is_available():
        result = coqui_tts_backend.synthesize(text=payload.text)
    else:
        result = mock_tts_backend.synthesize(text=payload.text)
    return {
        "backend": result["backend"], "duration_ms": result["duration_ms"], "format": result["format"],
        "audio_byte_length": len(result["audio_bytes"]),
    }


__all__ = ["router"]
