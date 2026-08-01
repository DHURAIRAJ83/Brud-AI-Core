"""Phase 18 public Smart Answer Router request/response schemas.

`PublicChatRequest` deliberately excludes any model/provider/RAG-space/
Admin-identifier override -- public users may only send a message, an
optional continuing `conversation_id`, a bounded language override
(`auto|ta|en`, never `tanglish`), a memory-consent flag, and an
optional client-generated idempotency tag. Unknown fields are rejected
(`extra="forbid"`, the existing repo-wide convention), never silently
ignored.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from backend.core.validation import DomainModel, validate_public_id
from core_model.public_chat import (
    CONFIDENCE_BANDS,
    EVIDENCE_STATUSES,
    EXECUTABLE_ROUTES,
    PUBLIC_FEEDBACK_TYPES,
    SAFETY_STATUSES,
    SOURCE_TYPES,
)

MAX_MESSAGE_LENGTH = 4000
MAX_COMMENT_LENGTH = 1000


class PublicChatRequest(DomainModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    conversation_id: str | None = None
    language_override: Literal["auto", "ta", "en"] = "auto"
    memory_consent: bool = False
    client_request_id: str | None = Field(default=None, max_length=128)

    @field_validator("conversation_id")
    @classmethod
    def _validate_conversation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_public_id(value)

    @field_validator("message")
    @classmethod
    def _strip_message(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("message must not be blank")
        return stripped


class PublicCitation(DomainModel):
    citation_id: str
    source_type: Literal["rag", "memory", "web"]
    title: str | None = None
    document_or_site_name: str | None = None
    page_or_section: str | None = None
    published_at: str | None = None
    updated_at: str | None = None
    retrieved_at: str | None = None
    verification_status: str
    support_status: str
    url: str | None = None


class PublicChatResponse(DomainModel):
    reply: str
    detected_language: str
    answer_language: str
    route_used: str
    route_reason_codes: list[str] = Field(default_factory=list)
    evidence_status: str
    confidence_band: str
    source_types: list[str] = Field(default_factory=list)
    citations: list[PublicCitation] = Field(default_factory=list)
    memory_used: bool = False
    clarification_required: bool = False
    insufficient_evidence: bool = False
    safety_status: str
    fallbacks_attempted: list[str] = Field(default_factory=list)
    request_id: str

    conversation_id: str | None = None
    model_assignment_public_name: str | None = None
    rag_space_public_name: str | None = None
    freshness_status: str | None = None
    limitations: list[str] = Field(default_factory=list)
    tool_name: str | None = None
    tool_version: str | None = None
    tool_status: str | None = None

    @field_validator("route_used")
    @classmethod
    def _validate_route_used(cls, value: str) -> str:
        if value not in EXECUTABLE_ROUTES:
            raise ValueError(f"route_used must be one of {EXECUTABLE_ROUTES}")
        return value

    @field_validator("evidence_status")
    @classmethod
    def _validate_evidence_status(cls, value: str) -> str:
        if value not in EVIDENCE_STATUSES:
            raise ValueError(f"evidence_status must be one of {EVIDENCE_STATUSES}")
        return value

    @field_validator("confidence_band")
    @classmethod
    def _validate_confidence_band(cls, value: str) -> str:
        if value not in CONFIDENCE_BANDS:
            raise ValueError(f"confidence_band must be one of {CONFIDENCE_BANDS}")
        return value

    @field_validator("safety_status")
    @classmethod
    def _validate_safety_status(cls, value: str) -> str:
        if value not in SAFETY_STATUSES:
            raise ValueError(f"safety_status must be one of {SAFETY_STATUSES}")
        return value

    @field_validator("source_types")
    @classmethod
    def _validate_source_types(cls, value: list[str]) -> list[str]:
        unknown = set(value) - set(SOURCE_TYPES)
        if unknown:
            raise ValueError(f"unknown source_types: {sorted(unknown)}")
        return value


class PublicChatCapabilities(DomainModel):
    core_model_available: bool
    approved_rag_available: bool
    memory_available: bool
    trusted_web_available: bool = False
    tool_available: bool = False
    calculator_available: bool = False
    unit_conversion_available: bool = False
    date_time_arithmetic_available: bool = False
    external_mcp_enabled: bool = False
    supported_input_languages: list[str] = Field(default_factory=lambda: ["ta", "en", "tanglish"])
    public_output_policy: str = "tamil_first"


class PublicChatFeedbackRequest(DomainModel):
    request_id: str
    route_used: str
    answer_hash: str
    feedback_type: str
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)

    @field_validator("feedback_type")
    @classmethod
    def _validate_feedback_type(cls, value: str) -> str:
        if value not in PUBLIC_FEEDBACK_TYPES:
            raise ValueError(f"feedback_type must be one of {PUBLIC_FEEDBACK_TYPES}")
        return value


__all__ = [
    "MAX_MESSAGE_LENGTH",
    "PublicChatCapabilities",
    "PublicChatFeedbackRequest",
    "PublicChatRequest",
    "PublicChatResponse",
    "PublicCitation",
]
