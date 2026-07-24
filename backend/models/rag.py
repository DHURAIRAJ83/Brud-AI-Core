"""Phase 16 RAG API request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from backend.core.validation import DomainModel


class KnowledgeSpaceCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str = Field(default="", max_length=4000)
    supported_languages: list[str] = Field(default_factory=lambda: ["ta", "en", "tgl", "mixed"])
    access_policy: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSpacePatch(DomainModel):
    description: str | None = Field(default=None, max_length=4000)
    supported_languages: list[str] | None = None
    access_policy: dict[str, Any] | None = None
    default_retrieval_profile_public_id: str | None = None
    lifecycle_status: str | None = Field(default=None, max_length=20)


class KnowledgeSourceCreate(DomainModel):
    source_type: str = Field(min_length=1, max_length=40)
    source_entity_public_id: str | None = None
    title: str = Field(min_length=1, max_length=300)
    language: str = Field(default="unknown", max_length=10)
    licence_status: str = Field(default="unknown", max_length=20)
    content: str | None = Field(default=None, max_length=2_000_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeSourcePatch(DomainModel):
    title: str | None = Field(default=None, max_length=300)
    licence_status: str | None = Field(default=None, max_length=20)
    approval_status: str | None = Field(default=None, max_length=20)
    metadata: dict[str, Any] | None = None


class ChunkSetCreate(DomainModel):
    chunking_strategy: str = Field(default="heading_aware", max_length=40)
    target_tokens: int = Field(default=350, ge=20, le=2000)
    maximum_tokens: int = Field(default=500, ge=20, le=4000)
    minimum_characters: int = Field(default=40, ge=1, le=2000)
    overlap_tokens: int = Field(default=50, ge=0, le=500)
    sentence_window_sentences: int = Field(default=3, ge=1, le=20)


class EmbeddingModelCreate(DomainModel):
    name: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=40)
    provider_type: str = Field(min_length=1, max_length=40)
    architecture: str = Field(default="", max_length=120)
    dimensions: int = Field(ge=2, le=4096)
    maximum_input_tokens: int = Field(ge=8, le=8192)
    supported_languages: list[str] = Field(default_factory=lambda: ["ta", "en", "tgl", "mixed"])


class EmbeddingRunCreate(DomainModel):
    embedding_model_public_id: str
    batch_size: int = Field(default=16, ge=1, le=256)


class VectorIndexCreate(DomainModel):
    distance_metric: str = Field(default="cosine", max_length=20)


class KeywordIndexCreate(DomainModel):
    pass


class RetrievalProfileCreate(DomainModel):
    name: str = Field(min_length=1, max_length=120)
    vector_top_k: int = Field(default=20, ge=1, le=200)
    keyword_top_k: int = Field(default=20, ge=1, le=200)
    final_top_k: int = Field(default=5, ge=1, le=50)
    vector_weight: float = Field(default=0.6, ge=0, le=1)
    keyword_weight: float = Field(default=0.4, ge=0, le=1)
    heading_boost: float = Field(default=0.05, ge=0, le=1)
    exact_match_boost: float = Field(default=0.1, ge=0, le=1)
    language_match_boost: float = Field(default=0.05, ge=0, le=1)
    source_priority: dict[str, float] = Field(default_factory=dict)
    minimum_score: float = Field(default=0.15, ge=0, le=1)
    deduplication_policy: str = Field(default="exact_only", max_length=20)
    diversity_policy: str = Field(default="none", max_length=20)
    context_token_budget: int = Field(default=800, ge=50, le=8000)
    injection_filter_policy: str = Field(default="block", max_length=20)
    no_answer_threshold: float = Field(default=0.2, ge=0, le=1)


class RetrievalProfilePatch(DomainModel):
    vector_top_k: int | None = Field(default=None, ge=1, le=200)
    keyword_top_k: int | None = Field(default=None, ge=1, le=200)
    final_top_k: int | None = Field(default=None, ge=1, le=50)
    vector_weight: float | None = Field(default=None, ge=0, le=1)
    keyword_weight: float | None = Field(default=None, ge=0, le=1)
    minimum_score: float | None = Field(default=None, ge=0, le=1)
    context_token_budget: int | None = Field(default=None, ge=50, le=8000)
    injection_filter_policy: str | None = Field(default=None, max_length=20)
    no_answer_threshold: float | None = Field(default=None, ge=0, le=1)


class RetrievalFiltersPayload(DomainModel):
    source_public_ids: list[str] = Field(default_factory=list)
    source_version_public_ids: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    record_types: list[str] = Field(default_factory=list)
    licence_statuses: list[str] = Field(default_factory=list)
    approval_statuses: list[str] = Field(default_factory=lambda: ["approved"])


class RetrieveRequest(DomainModel):
    retrieval_profile_public_id: str
    query: str = Field(min_length=1, max_length=2000)
    filters: RetrievalFiltersPayload = Field(default_factory=RetrievalFiltersPayload)


class GroundedAnswerRequest(DomainModel):
    retrieval_profile_public_id: str
    assignment_public_id: str
    query: str = Field(min_length=1, max_length=2000)
    filters: RetrievalFiltersPayload = Field(default_factory=RetrievalFiltersPayload)
    session_public_id: str | None = None


class RagSessionCreate(DomainModel):
    retrieval_profile_public_id: str
    assignment_public_id: str
    max_turns: int = Field(default=10, ge=1, le=100)


class RagSessionMessageCreate(DomainModel):
    message: str = Field(min_length=1, max_length=2000)
    retrieval_profile_public_id: str


class EvaluationSuiteCreate(DomainModel):
    name: str = Field(min_length=1, max_length=160)
    version: str = Field(min_length=1, max_length=40)
    evaluation_type: str = Field(default="both", max_length=20)


class EvaluationFixtureCreate(DomainModel):
    query: str = Field(min_length=1, max_length=2000)
    language: str = Field(default="unknown", max_length=10)
    expected_relevant_chunk_ids: list[str] = Field(default_factory=list)
    expected_relevant_source_ids: list[str] = Field(default_factory=list)
    expected_no_answer: bool = False
    required_keywords: list[str] = Field(default_factory=list)
    forbidden_claims: list[str] = Field(default_factory=list)
    expected_answer_language: str | None = None
    injection_test: bool = False
    severity: str = Field(default="info", max_length=20)


class EvaluationRunCreate(DomainModel):
    retrieval_profile_public_id: str | None = None
    assignment_public_id: str | None = None


class IndexComparisonRequest(DomainModel):
    left_vector_index_public_id: str | None = None
    right_vector_index_public_id: str | None = None
    left_keyword_index_public_id: str | None = None
    right_keyword_index_public_id: str | None = None
    evaluation_suite_public_id: str | None = None
