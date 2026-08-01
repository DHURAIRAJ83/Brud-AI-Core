"""Phase 19 Admin-only knowledge-gap registry request schemas."""

from __future__ import annotations

from pydantic import Field, field_validator

from backend.core.validation import DomainModel
from core_model.knowledge_gap import RESEARCH_NOTE_TYPES, RESOLUTION_TYPES, REVIEW_DECISIONS

MAX_COMMENT_LENGTH = 2000
MAX_NOTE_LENGTH = 4000
MAX_REASON_LENGTH = 500


class GapReviewRequest(DomainModel):
    decision: str
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)

    @field_validator("decision")
    @classmethod
    def _validate_decision(cls, value: str) -> str:
        if value not in REVIEW_DECISIONS:
            raise ValueError(f"decision must be one of {REVIEW_DECISIONS}")
        return value


class GapClassifyRequest(DomainModel):
    comment: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)


class GapNoteRequest(DomainModel):
    note_type: str
    note_text: str = Field(min_length=1, max_length=MAX_NOTE_LENGTH)
    source_reference: str | None = Field(default=None, max_length=500)

    @field_validator("note_type")
    @classmethod
    def _validate_note_type(cls, value: str) -> str:
        if value not in RESEARCH_NOTE_TYPES:
            raise ValueError(f"note_type must be one of {RESEARCH_NOTE_TYPES}")
        return value


class GapResolveRequest(DomainModel):
    resolution_type: str
    notes: str | None = Field(default=None, max_length=MAX_COMMENT_LENGTH)

    @field_validator("resolution_type")
    @classmethod
    def _validate_resolution_type(cls, value: str) -> str:
        if value not in RESOLUTION_TYPES:
            raise ValueError(f"resolution_type must be one of {RESOLUTION_TYPES}")
        return value


class GapProposeMergeRequest(DomainModel):
    case_public_ids: list[str] = Field(min_length=2, max_length=20)


class GapConfirmMergeRequest(DomainModel):
    case_public_ids: list[str] = Field(min_length=2, max_length=20)
    stale_check_fingerprint: str
    canonical_question: str = Field(min_length=1, max_length=2000)
    primary_language: str = Field(min_length=2, max_length=10)


class GapDeletionRequest(DomainModel):
    reason: str | None = Field(default=None, max_length=MAX_REASON_LENGTH)


__all__ = [
    "GapClassifyRequest",
    "GapConfirmMergeRequest",
    "GapDeletionRequest",
    "GapNoteRequest",
    "GapProposeMergeRequest",
    "GapResolveRequest",
    "GapReviewRequest",
]
