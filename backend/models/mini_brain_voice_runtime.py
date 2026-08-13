"""MB-26: Voice & Speech Runtime API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from backend.core.validation import DomainModel, validate_public_id

MAX_AUDIO_BASE64_LENGTH = 12_000_000  # ~9MB decoded, comfortably above the default 8MB audio ceiling
MAX_TRANSCRIPT_TEXT_LENGTH = 1000


class CreateVoiceSessionRequest(DomainModel):
    session_mode: Literal["public_chat", "admin_assistant"] = "public_chat"
    explicit_consent: bool = False
    conversation_id: str | None = None
    language_override: Literal["auto", "ta", "en"] = "auto"

    @field_validator("conversation_id")
    @classmethod
    def _validate_conversation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_public_id(value)


class VoiceChunkRequest(DomainModel):
    sequence: int = Field(ge=0, le=10_000)
    audio_base64: str = Field(min_length=1, max_length=MAX_AUDIO_BASE64_LENGTH)


class FinishVoiceSessionRequest(DomainModel):
    pass


class VoiceSessionResponse(DomainModel):
    public_id: str
    session_mode: str
    stage: str
    status: str
    transcript: str | None = None
    reply: str | None = None
    tts_audio_relative_path: str | None = None
    denial_reason: str | None = None


class TestSttRequest(DomainModel):
    audio_base64: str = Field(min_length=1, max_length=MAX_AUDIO_BASE64_LENGTH)


class TestTtsRequest(DomainModel):
    text: str = Field(min_length=1, max_length=MAX_TRANSCRIPT_TEXT_LENGTH)
