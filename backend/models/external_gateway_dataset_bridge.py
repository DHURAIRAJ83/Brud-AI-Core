"""MB-40/MB-41: External AI Gateway -> Dataset Studio -> RAG bridge API
schemas."""

from __future__ import annotations

from pydantic import Field

from backend.core.validation import DomainModel


class ExportAcceptedSessionRequest(DomainModel):
    target_source_public_id: str | None = None
    ingest_to_rag: bool = False
    rag_knowledge_space_public_id: str | None = None
    build_rag_index: bool = False
    retrieval_profile_name: str | None = None


class ExportAcceptedSessionResponse(DomainModel):
    session_public_id: str
    dataset_source_public_id: str
    created_record_public_ids: list[str] = Field(default_factory=list)
    duplicate_provider_run_public_ids: list[str] = Field(default_factory=list)
    skipped_provider_run_public_ids: list[str] = Field(default_factory=list)
    rag_source_public_ids: list[str] = Field(default_factory=list)
    ingest_to_rag: bool
    source_version_public_ids: list[str] = Field(default_factory=list)
    chunk_set_public_ids: list[str] = Field(default_factory=list)
    embedding_run_public_ids: list[str] = Field(default_factory=list)
    vector_index_public_ids: list[str] = Field(default_factory=list)
    retrieval_profile_public_id: str | None = None
