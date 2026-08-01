"""Request/response models for the Phase 5 Semantic Chunk & Structured
Record Studio."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from backend.core.validation import DomainModel

ChunkType = Literal[
    "heading",
    "subheading",
    "paragraph",
    "definition",
    "example",
    "dictionary_entry",
    "grammar_rule",
    "question",
    "answer",
    "instruction",
    "response",
    "translation_source",
    "translation_target",
    "tanglish_text",
    "tamil_text",
    "english_text",
    "table",
    "table_row",
    "list",
    "footnote",
    "caption",
    "reference",
    "metadata",
    "irrelevant",
    "unknown",
]

RecordType = Literal[
    "plain_text",
    "language_example",
    "conversation",
    "question_answer",
    "instruction_response",
    "dictionary_entry",
    "translation_pair",
    "tanglish_normalization",
    "knowledge_note",
    "grammar_example",
    "rag_chunk",
]

TargetUse = Literal[
    "rag", "training", "evaluation", "commercial", "public_export", "redistribution"
]

ReviewStatus = Literal["approved", "rejected", "changes_requested"]


class ManualChunkCreate(DomainModel):
    text: str = Field(min_length=1, max_length=100_000)
    chunk_type: ChunkType = "paragraph"
    page_number: int = Field(gt=0)
    language: str = "unknown"


class ClassifyRequest(DomainModel):
    chunk_type: ChunkType
    notes: str = Field(default="", max_length=2000)


class AssignParentRequest(DomainModel):
    parent_chunk_public_id: str | None = None


class ReorderRequest(DomainModel):
    chunk_public_ids: list[str] = Field(min_length=1)


class SplitRequest(DomainModel):
    split_at: int = Field(ge=0)


class MergeRequest(DomainModel):
    other_chunk_public_id: str


class MoveBoundaryRequest(DomainModel):
    neighbor_chunk_public_id: str
    edge: Literal["start", "end"]
    new_offset: int = Field(ge=0)


class EditTextRequest(DomainModel):
    text: str = Field(min_length=1, max_length=100_000)
    change_summary: str = Field(default="", max_length=2000)


class ReviewActionRequest(DomainModel):
    notes: str = Field(default="", max_length=2000)


class CreateStructuredRecordRequest(DomainModel):
    record_type: RecordType
    chunk_public_ids: list[str] = Field(min_length=1)
    fields: dict[str, Any] = Field(default_factory=dict)
    requested_uses: list[TargetUse] = Field(default_factory=list)


class ReviseStructuredRecordRequest(DomainModel):
    fields: dict[str, Any] = Field(default_factory=dict)
    change_summary: str = Field(default="", max_length=2000)


class StructuredRecordReviewRequest(DomainModel):
    review_status: ReviewStatus
    comments: str = Field(default="", max_length=2000)


class UsageCheckRequest(DomainModel):
    target_use: TargetUse
