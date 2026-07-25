"""Phase 17 conversation-memory API request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class MemoryPolicyCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    default_session_mode: str = Field(default="private_no_persist", max_length=30)
    allow_short_term_context: bool = True
    allow_session_summary: bool = True
    allow_long_term_memory: bool = False
    require_explicit_consent: bool = True
    maximum_session_turns: int = Field(default=20, ge=1, le=500)
    maximum_session_age_seconds: int = Field(default=3600, ge=60, le=86400)
    maximum_short_term_tokens: int = Field(default=800, ge=50, le=8000)
    maximum_summary_tokens: int = Field(default=200, ge=20, le=2000)
    maximum_memory_items: int = Field(default=50, ge=1, le=1000)
    default_memory_ttl_seconds: int = Field(default=7_776_000, ge=60, le=31_536_000)
    allowed_memory_categories: list[str] = Field(default_factory=list)
    forbidden_content_categories: list[str] = Field(default_factory=list)
    retrieval_configuration: dict[str, Any] = Field(default_factory=dict)


class MemoryPolicyPatch(DomainModel):
    description: str | None = Field(default=None, max_length=2000)
    allow_long_term_memory: bool | None = None
    maximum_session_turns: int | None = Field(default=None, ge=1, le=500)
    allowed_memory_categories: list[str] | None = None
    lifecycle_status: str | None = Field(default=None, max_length=20)


class SessionCreate(DomainModel):
    session_mode: str = Field(min_length=1, max_length=30)
    memory_policy_public_id: str
    participant_type: str = Field(default="admin", max_length=30)
    participant_scope_key: str = Field(min_length=1, max_length=200)
    language_preference: str = Field(default="unknown", max_length=10)
    model_assignment_public_id: str | None = None
    rag_retrieval_profile_public_id: str | None = None


class MessageCreate(DomainModel):
    message: str = Field(min_length=1, max_length=4000)
    explicit_language_request: str | None = Field(default=None, max_length=10)
    memory_retrieval_profile_public_id: str | None = None


class SummaryCreate(DomainModel):
    generation_method: str = Field(default="deterministic_extract", max_length=30)


class ConsentCreate(DomainModel):
    participant_scope_key: str = Field(min_length=1, max_length=200)
    memory_policy_public_id: str
    purpose: str = Field(min_length=1, max_length=60)
    allowed_categories: list[str] = Field(default_factory=list)
    prohibited_categories: list[str] = Field(default_factory=list)
    expires_at: str | None = None


class MemoryItemCreate(DomainModel):
    participant_scope_key: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=60)
    purpose: str = Field(min_length=1, max_length=60)
    creation_source: str = Field(min_length=1, max_length=40)
    confidence_type: str = Field(min_length=1, max_length=40)
    display_value: str = Field(min_length=1, max_length=2000)
    consent_public_id: str | None = None
    source_session_public_id: str | None = None
    source_turn_public_id: str | None = None
    expires_at: str | None = None


class MemoryItemCorrect(DomainModel):
    display_value: str = Field(min_length=1, max_length=2000)
    change_reason: str = Field(min_length=1, max_length=200)


class RetrievalProfileCreate(DomainModel):
    name: str = Field(min_length=1, max_length=120)
    allowed_categories: list[str] = Field(default_factory=list)
    allowed_purposes: list[str] = Field(default_factory=list)
    keyword_weight: float = Field(default=0.4, ge=0, le=1)
    vector_weight: float = Field(default=0.6, ge=0, le=1)
    recency_weight: float = Field(default=0.1, ge=0, le=1)
    user_confirmed_boost: float = Field(default=0.2, ge=0, le=1)
    maximum_results: int = Field(default=5, ge=1, le=50)
    minimum_score: float = Field(default=0.15, ge=0, le=1)
    maximum_memory_tokens: int = Field(default=200, ge=20, le=4000)
    conflict_policy: str = Field(default="prefer_recent", max_length=30)


class RetrievalProfilePatch(DomainModel):
    keyword_weight: float | None = Field(default=None, ge=0, le=1)
    vector_weight: float | None = Field(default=None, ge=0, le=1)
    maximum_results: int | None = Field(default=None, ge=1, le=50)
    minimum_score: float | None = Field(default=None, ge=0, le=1)
    conflict_policy: str | None = Field(default=None, max_length=30)


class MemoryRetrieveRequest(DomainModel):
    retrieval_profile_public_id: str
    participant_scope_key: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=2000)


class EvaluationSuiteCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=40)


class EvaluationFixtureCreate(DomainModel):
    participant_scope_key: str = Field(min_length=1, max_length=200)
    session_mode: str = Field(default="consented_memory", max_length=30)
    query: str = Field(min_length=1, max_length=2000)
    query_language: str = Field(default="unknown", max_length=10)
    expected_retrieved_memory_ids: list[str] = Field(default_factory=list)
    expected_excluded_memory_ids: list[str] = Field(default_factory=list)
    expected_language: str | None = None
    expected_rag_use: bool = False
    expected_no_memory_behavior: bool = False
    expected_response_status: str | None = None
    injection_test: bool = False
    severity: str = Field(default="info", max_length=20)


class EvaluationRunCreate(DomainModel):
    retrieval_profile_public_id: str | None = None
