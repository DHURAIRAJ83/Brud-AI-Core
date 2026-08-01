"""Request/response models for the Phase 3 Manual Data Studio."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from backend.core.validation import DomainModel
from backend.models.data_sources import DataSourceCreate

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
    "evaluation_case_draft",
]

RecordStatus = Literal[
    "draft",
    "needs_review",
    "needs_source_verification",
    "needs_domain_review",
    "approved",
    "rejected",
    "archived",
]

CreationMethod = Literal[
    "human_created",
    "admin_created",
    "teacher_created",
    "ai_assisted",
    "imported_manual",
    "derived_manual",
]

FactDependency = Literal["none", "low", "medium", "high"]

KnowledgeRisk = Literal[
    "language_only", "general", "domain_specific", "high_risk", "time_sensitive"
]

LanguageCode = Literal["ta", "en", "tgl", "mixed", "unknown"]

TargetUse = Literal[
    "rag", "training", "evaluation", "commercial", "public_export", "redistribution"
]

ReviewType = Literal["language", "translation", "factual", "domain", "general"]

ReviewStatus = Literal["approved", "rejected", "changes_requested"]

VerificationType = Literal[
    "source_verification",
    "factual_verification",
    "domain_verification",
    "time_sensitivity_revalidation",
]

VerificationStatus = Literal["pending", "verified", "rejected", "expired"]


class ConversationTurn(DomainModel):
    role: str = Field(min_length=1, max_length=40)
    language: str | None = None
    content: str = Field(min_length=1, max_length=20_000)


class ManualRecordContentInput(DomainModel):
    title: str | None = Field(default=None, max_length=300)
    input_text: str | None = Field(default=None, max_length=100_000)
    output_text: str | None = Field(default=None, max_length=100_000)
    instruction_text: str | None = Field(default=None, max_length=20_000)
    response_text: str | None = Field(default=None, max_length=100_000)
    question_text: str | None = Field(default=None, max_length=20_000)
    answer_text: str | None = Field(default=None, max_length=100_000)
    tamil_text: str | None = Field(default=None, max_length=100_000)
    english_text: str | None = Field(default=None, max_length=100_000)
    tanglish_text: str | None = Field(default=None, max_length=100_000)
    word: str | None = Field(default=None, max_length=300)
    part_of_speech: str | None = Field(default=None, max_length=50)
    meanings: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    turns: list[ConversationTurn] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ManualDataRecordCreate(DomainModel):
    record_type: RecordType
    primary_language: LanguageCode = "unknown"
    input_language: LanguageCode | None = None
    output_language: LanguageCode | None = None
    domain: str = Field(default="", max_length=200)
    topic: str = Field(default="", max_length=200)
    difficulty: str | None = Field(default=None, max_length=50)
    audience: str | None = Field(default=None, max_length=50)
    style: str | None = Field(default=None, max_length=100)
    fact_dependency: FactDependency = "none"
    knowledge_risk: KnowledgeRisk = "language_only"
    creation_method: CreationMethod = "admin_created"
    requested_uses: list[TargetUse] = Field(default_factory=list)
    review_expiry_at: str | None = None
    source_public_id: str | None = None
    new_source: DataSourceCreate | None = None
    content: ManualRecordContentInput
    change_summary: str = Field(default="", max_length=2000)


class ManualDataRecordPatch(DomainModel):
    domain: str | None = Field(default=None, max_length=200)
    topic: str | None = Field(default=None, max_length=200)
    difficulty: str | None = Field(default=None, max_length=50)
    audience: str | None = Field(default=None, max_length=50)
    style: str | None = Field(default=None, max_length=100)
    requested_uses: list[TargetUse] | None = None
    review_expiry_at: str | None = None


class RevisionCreate(DomainModel):
    content: ManualRecordContentInput
    change_summary: str = Field(default="", max_length=2000)


class ReviewRequest(DomainModel):
    review_type: ReviewType
    review_status: ReviewStatus
    comments: str = Field(default="", max_length=4000)
    language_score: float | None = Field(default=None, ge=0, le=100)
    meaning_score: float | None = Field(default=None, ge=0, le=100)
    naturalness_score: float | None = Field(default=None, ge=0, le=100)
    factual_score: float | None = Field(default=None, ge=0, le=100)
    source_score: float | None = Field(default=None, ge=0, le=100)
    overall_score: float | None = Field(default=None, ge=0, le=100)


class VerificationRequest(DomainModel):
    verification_type: VerificationType
    verification_status: VerificationStatus = "pending"
    source_public_id: str | None = None
    verification_notes: str = Field(default="", max_length=4000)


class ApprovalRequest(DomainModel):
    approved_uses: list[TargetUse] = Field(default_factory=list)
    notes: str = Field(default="", max_length=2000)


class RejectRequest(DomainModel):
    reason: str = Field(default="", max_length=2000)


class UsageCheckRequest(DomainModel):
    target_use: TargetUse


class CreateCandidateRequest(DomainModel):
    notes: str = Field(default="", max_length=2000)
