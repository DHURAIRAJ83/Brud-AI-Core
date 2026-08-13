"""Repository for Phase 16 RAG knowledge spaces, sources, chunking,
embeddings, vector/keyword indexes, retrieval, grounded generation,
evaluation, comparison, and manifests."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "knowledge_space_id",
    "knowledge_source_id",
    "source_version_id",
    "chunk_set_id",
    "chunk_id",
    "embedding_model_id",
    "embedding_run_id",
    "vector_index_id",
    "keyword_index_id",
    "retrieval_profile_id",
    "retrieval_run_id",
    "context_assembly_id",
    "grounded_request_id",
    "grounded_answer_id",
    "evaluation_suite_id",
    "evaluation_run_id",
    "model_assignment_id",
    "session_id",
    "source_id",
    "left_vector_index_id",
    "right_vector_index_id",
    "left_keyword_index_id",
    "right_keyword_index_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("rag row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class RagRepository(BaseRepository):
    # --- knowledge spaces -----------------------------------------------------

    def create_space(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_knowledge_spaces(public_id,name,slug,description,
            supported_languages_json,access_policy_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values["slug"],
                values.get("description", ""),
                values["supported_languages_json"],
                values["access_policy_json"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def space(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM rag_knowledge_spaces WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("knowledge space not found")
        return row

    def list_spaces(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_knowledge_spaces ORDER BY created_at DESC,id DESC"
        ).fetchall()

    def update_space(
        self, connection: sqlite3.Connection, space_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE rag_knowledge_spaces SET {columns},updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), space_id),
        )

    # --- knowledge sources -----------------------------------------------------

    def create_source(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_knowledge_sources(public_id,knowledge_space_id,source_type,
            source_entity_public_id,title,language,licence_status,metadata_json,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["knowledge_space_id"],
                values["source_type"],
                values.get("source_entity_public_id"),
                values["title"],
                values.get("language", "unknown"),
                values.get("licence_status", "unknown"),
                values.get("metadata_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def source(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT s.*, sp.public_id AS knowledge_space_public_id
            FROM rag_knowledge_sources s
            JOIN rag_knowledge_spaces sp ON sp.id=s.knowledge_space_id
            WHERE s.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("knowledge source not found")
        return row

    def sources_for_space(
        self, connection: sqlite3.Connection, space_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_knowledge_sources WHERE knowledge_space_id=? ORDER BY created_at",
            (space_id,),
        ).fetchall()

    def update_source(
        self, connection: sqlite3.Connection, source_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE rag_knowledge_sources SET {columns},updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), source_id),
        )

    # --- source versions -----------------------------------------------------

    def create_source_version(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        next_version = connection.execute(
            "SELECT COALESCE(MAX(version_number),0)+1 FROM rag_source_versions "
            "WHERE knowledge_source_id=?",
            (values["knowledge_source_id"],),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO rag_source_versions(public_id,knowledge_source_id,version_number,
            content_checksum_sha256,extraction_method,extraction_version,
            normalized_content_checksum_sha256,character_count,token_estimate,
            language_distribution_json,status,raw_content,normalized_content)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["knowledge_source_id"],
                next_version,
                values["content_checksum_sha256"],
                values.get("extraction_method", "direct"),
                values.get("extraction_version", "v1"),
                values.get("normalized_content_checksum_sha256"),
                values.get("character_count", 0),
                values.get("token_estimate", 0),
                values.get("language_distribution_json", "{}"),
                values.get("status", "processing"),
                values["raw_content"],
                values.get("normalized_content"),
            ),
        )
        return public_id

    def source_version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT v.*, s.public_id AS knowledge_source_public_id,
            s.approval_status AS source_approval_status, s.licence_status AS source_licence_status,
            s.language AS source_language
            FROM rag_source_versions v JOIN rag_knowledge_sources s ON s.id=v.knowledge_source_id
            WHERE v.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("source version not found")
        return row

    def versions_for_source(
        self, connection: sqlite3.Connection, source_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_source_versions WHERE knowledge_source_id=? ORDER BY version_number",
            (source_id,),
        ).fetchall()

    def latest_source_version(
        self, connection: sqlite3.Connection, source_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM rag_source_versions WHERE knowledge_source_id=? "
            "ORDER BY version_number DESC LIMIT 1",
            (source_id,),
        ).fetchone()

    def update_source_version(
        self, connection: sqlite3.Connection, version_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE rag_source_versions SET {columns} WHERE id=?", (*fields.values(), version_id)
        )

    # --- chunk sets -----------------------------------------------------

    def create_chunk_set(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_chunk_sets(public_id,source_version_id,chunking_strategy,
            configuration_json,created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["source_version_id"],
                values.get("chunking_strategy", "heading_aware"),
                values.get("configuration_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def chunk_set(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT cs.*, v.public_id AS source_version_public_id,
            s.public_id AS knowledge_source_public_id
            FROM rag_chunk_sets cs
            JOIN rag_source_versions v ON v.id=cs.source_version_id
            JOIN rag_knowledge_sources s ON s.id=v.knowledge_source_id
            WHERE cs.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("chunk set not found")
        return row

    def chunk_sets_for_version(
        self, connection: sqlite3.Connection, version_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_chunk_sets WHERE source_version_id=? ORDER BY created_at",
            (version_id,),
        ).fetchall()

    def update_chunk_set(
        self, connection: sqlite3.Connection, chunk_set_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE rag_chunk_sets SET {columns},updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), chunk_set_id),
        )

    # --- chunks -----------------------------------------------------

    def record_chunk(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_chunks(public_id,chunk_set_id,source_version_id,sequence_number,
            heading_path_json,source_location_json,language,record_type,normalized_text,
            character_count,estimated_token_count,overlap_before_tokens,overlap_after_tokens,
            content_checksum_sha256,quality_status,quality_issues_json,injection_status,
            injection_reasons_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["chunk_set_id"],
                values["source_version_id"],
                values["sequence_number"],
                values.get("heading_path_json", "[]"),
                values.get("source_location_json", "{}"),
                values.get("language", "unknown"),
                values.get("record_type"),
                values["normalized_text"],
                values.get("character_count", 0),
                values.get("estimated_token_count", 0),
                values.get("overlap_before_tokens", 0),
                values.get("overlap_after_tokens", 0),
                values["content_checksum_sha256"],
                values["quality_status"],
                values.get("quality_issues_json", "[]"),
                values.get("injection_status", "clean"),
                values.get("injection_reasons_json", "[]"),
            ),
        )
        return public_id

    def chunks_for_set(
        self, connection: sqlite3.Connection, chunk_set_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_chunks WHERE chunk_set_id=? ORDER BY sequence_number",
            (chunk_set_id,),
        ).fetchall()

    def chunk_by_public_id(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM rag_chunks WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("chunk not found")
        return row

    # --- embedding models -----------------------------------------------------

    def create_embedding_model(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_embedding_models(public_id,name,version,provider_type,
            architecture,dimensions,maximum_input_tokens,supported_languages_json,
            artifact_checksum,configuration_checksum,lifecycle_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["name"],
                values["version"],
                values["provider_type"],
                values.get("architecture", ""),
                values["dimensions"],
                values["maximum_input_tokens"],
                values.get("supported_languages_json", "[]"),
                values.get("artifact_checksum"),
                values.get("configuration_checksum"),
                values.get("lifecycle_status", "validated"),
            ),
        )
        return public_id

    def embedding_model(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM rag_embedding_models WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("embedding model not found")
        return row

    def list_embedding_models(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_embedding_models ORDER BY created_at DESC,id DESC"
        ).fetchall()

    # --- embedding runs -----------------------------------------------------

    def create_embedding_run(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_embedding_runs(public_id,chunk_set_id,embedding_model_id,
            configuration_json,total_chunks,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["chunk_set_id"],
                values["embedding_model_id"],
                values.get("configuration_json", "{}"),
                values.get("total_chunks", 0),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def embedding_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT r.*, cs.public_id AS chunk_set_public_id,
            m.public_id AS embedding_model_public_id, m.dimensions AS model_dimensions,
            m.provider_type AS model_provider_type
            FROM rag_embedding_runs r
            JOIN rag_chunk_sets cs ON cs.id=r.chunk_set_id
            JOIN rag_embedding_models m ON m.id=r.embedding_model_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("embedding run not found")
        return row

    def update_embedding_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE rag_embedding_runs SET {columns} WHERE id=?", (*fields.values(), run_id)
        )

    # --- chunk embeddings -----------------------------------------------------

    def record_chunk_embedding(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_chunk_embeddings(public_id,embedding_run_id,chunk_id,dimensions,
            vector_norm,vector_checksum_sha256,vector_blob) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["embedding_run_id"],
                values["chunk_id"],
                values["dimensions"],
                values["vector_norm"],
                values["vector_checksum_sha256"],
                values["vector_blob"],
            ),
        )
        return public_id

    def embeddings_for_run(
        self, connection: sqlite3.Connection, embedding_run_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_chunk_embeddings WHERE embedding_run_id=? ORDER BY id",
            (embedding_run_id,),
        ).fetchall()

    # --- vector indexes -----------------------------------------------------

    def create_vector_index(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_vector_indexes(public_id,knowledge_space_id,chunk_set_id,
            embedding_run_id,distance_metric,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["knowledge_space_id"],
                values["chunk_set_id"],
                values["embedding_run_id"],
                values.get("distance_metric", "cosine"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def vector_index(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT vi.*, sp.public_id AS knowledge_space_public_id,
            cs.public_id AS chunk_set_public_id, er.public_id AS embedding_run_public_id
            FROM rag_vector_indexes vi
            JOIN rag_knowledge_spaces sp ON sp.id=vi.knowledge_space_id
            JOIN rag_chunk_sets cs ON cs.id=vi.chunk_set_id
            JOIN rag_embedding_runs er ON er.id=vi.embedding_run_id
            WHERE vi.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("vector index not found")
        return row

    def update_vector_index(
        self, connection: sqlite3.Connection, index_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE rag_vector_indexes SET {columns} WHERE id=?", (*fields.values(), index_id)
        )

    def active_vector_index_for_space(
        self, connection: sqlite3.Connection, space_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM rag_vector_indexes WHERE knowledge_space_id=? AND status='active' "
            "ORDER BY activated_at DESC LIMIT 1",
            (space_id,),
        ).fetchone()

    def latest_vector_index_for_space(
        self, connection: sqlite3.Connection, space_id: int
    ) -> sqlite3.Row | None:
        # MB-43: unlike active_vector_index_for_space (active only), this
        # returns the most recent index regardless of status, so the
        # Retrieval Profile Management UI can show its real current state
        # (e.g. "validated, not yet active") rather than nothing at all.
        return connection.execute(
            "SELECT * FROM rag_vector_indexes WHERE knowledge_space_id=? "
            "ORDER BY created_at DESC, id DESC LIMIT 1",
            (space_id,),
        ).fetchone()

    # --- keyword indexes -----------------------------------------------------

    def create_keyword_index(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_keyword_indexes(public_id,knowledge_space_id,chunk_set_id,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                public_id,
                values["knowledge_space_id"],
                values["chunk_set_id"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def keyword_index(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT ki.*, sp.public_id AS knowledge_space_public_id,
            cs.public_id AS chunk_set_public_id
            FROM rag_keyword_indexes ki
            JOIN rag_knowledge_spaces sp ON sp.id=ki.knowledge_space_id
            JOIN rag_chunk_sets cs ON cs.id=ki.chunk_set_id
            WHERE ki.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("keyword index not found")
        return row

    def update_keyword_index(
        self, connection: sqlite3.Connection, index_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE rag_keyword_indexes SET {columns} WHERE id=?", (*fields.values(), index_id)
        )

    def active_keyword_index_for_space(
        self, connection: sqlite3.Connection, space_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM rag_keyword_indexes WHERE knowledge_space_id=? AND status='active' "
            "ORDER BY activated_at DESC LIMIT 1",
            (space_id,),
        ).fetchone()

    # --- retrieval profiles -----------------------------------------------------

    def create_retrieval_profile(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_retrieval_profiles(public_id,knowledge_space_id,name,
            vector_top_k,keyword_top_k,final_top_k,vector_weight,keyword_weight,heading_boost,
            exact_match_boost,language_match_boost,source_priority_json,minimum_score,
            deduplication_policy,diversity_policy,context_token_budget,injection_filter_policy,
            no_answer_threshold,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["knowledge_space_id"],
                values["name"],
                values.get("vector_top_k", 20),
                values.get("keyword_top_k", 20),
                values.get("final_top_k", 5),
                values.get("vector_weight", 0.6),
                values.get("keyword_weight", 0.4),
                values.get("heading_boost", 0.05),
                values.get("exact_match_boost", 0.1),
                values.get("language_match_boost", 0.05),
                values.get("source_priority_json", "{}"),
                values.get("minimum_score", 0.15),
                values.get("deduplication_policy", "exact_only"),
                values.get("diversity_policy", "none"),
                values.get("context_token_budget", 800),
                values.get("injection_filter_policy", "block"),
                values.get("no_answer_threshold", 0.2),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def retrieval_profile(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT p.*, sp.public_id AS knowledge_space_public_id
            FROM rag_retrieval_profiles p JOIN rag_knowledge_spaces sp ON sp.id=p.knowledge_space_id
            WHERE p.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("retrieval profile not found")
        return row

    def profiles_for_space(
        self, connection: sqlite3.Connection, space_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_retrieval_profiles WHERE knowledge_space_id=? ORDER BY created_at",
            (space_id,),
        ).fetchall()

    def list_retrieval_profiles(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        # MB-43: joins in the owning space's public_id/name (additive
        # columns only) so the Retrieval Profile Management UI can show
        # "knowledge space name" without an extra round trip per row --
        # every existing caller of list_profiles() is unaffected since no
        # column is removed or renamed.
        return connection.execute(
            """SELECT p.*, sp.public_id AS knowledge_space_public_id, sp.name AS knowledge_space_name
            FROM rag_retrieval_profiles p JOIN rag_knowledge_spaces sp ON sp.id=p.knowledge_space_id
            ORDER BY p.created_at DESC, p.id DESC"""
        ).fetchall()

    def update_retrieval_profile(
        self, connection: sqlite3.Connection, profile_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE rag_retrieval_profiles SET {columns},updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), profile_id),
        )

    # --- retrieval runs -----------------------------------------------------

    def create_retrieval_run(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_retrieval_runs(public_id,retrieval_profile_id,knowledge_space_id,
            vector_index_id,keyword_index_id,normalized_query,query_checksum_sha256,
            query_language,filters_json,top_k_configuration_json,runtime_milliseconds,
            total_candidates,final_result_count,no_answer_score,status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["retrieval_profile_id"],
                values["knowledge_space_id"],
                values.get("vector_index_id"),
                values.get("keyword_index_id"),
                values["normalized_query"],
                values["query_checksum_sha256"],
                values.get("query_language", "unknown"),
                values.get("filters_json", "{}"),
                values.get("top_k_configuration_json", "{}"),
                values.get("runtime_milliseconds"),
                values.get("total_candidates", 0),
                values.get("final_result_count", 0),
                values.get("no_answer_score"),
                values.get("status", "completed"),
            ),
        )
        return public_id

    def retrieval_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM rag_retrieval_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("retrieval run not found")
        return row

    # --- retrieved chunks -----------------------------------------------------

    def record_retrieved_chunk(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_retrieved_chunks(public_id,retrieval_run_id,rank,chunk_id,
            source_id,source_version_id,vector_score,keyword_score,combined_score,rerank_score,
            injection_status,filter_evidence_json,selected_for_context,exclusion_reason)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["retrieval_run_id"],
                values["rank"],
                values["chunk_id"],
                values["source_id"],
                values["source_version_id"],
                values.get("vector_score"),
                values.get("keyword_score"),
                values.get("combined_score"),
                values.get("rerank_score"),
                values.get("injection_status", "clean"),
                values.get("filter_evidence_json", "{}"),
                1 if values.get("selected_for_context") else 0,
                values.get("exclusion_reason"),
            ),
        )
        return public_id

    def retrieved_chunks_for_run(
        self, connection: sqlite3.Connection, retrieval_run_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_retrieved_chunks WHERE retrieval_run_id=? ORDER BY rank",
            (retrieval_run_id,),
        ).fetchall()

    # --- context assemblies -----------------------------------------------------

    def record_context_assembly(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_context_assemblies(public_id,retrieval_run_id,
            maximum_model_context,prompt_template_tokens,query_tokens,retrieved_context_tokens,
            reserved_output_tokens,safety_margin_tokens,dropped_chunk_count,
            final_context_checksum_sha256,citation_map_json) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["retrieval_run_id"],
                values["maximum_model_context"],
                values.get("prompt_template_tokens", 0),
                values.get("query_tokens", 0),
                values.get("retrieved_context_tokens", 0),
                values.get("reserved_output_tokens", 0),
                values.get("safety_margin_tokens", 0),
                values.get("dropped_chunk_count", 0),
                values.get("final_context_checksum_sha256"),
                values.get("citation_map_json", "{}"),
            ),
        )
        return public_id

    def context_assembly(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM rag_context_assemblies WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("context assembly not found")
        return row

    # --- grounded requests/answers -----------------------------------------------------

    def create_grounded_request(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_grounded_requests(public_id,context_assembly_id,retrieval_run_id,
            model_assignment_id,scope,session_id,query_checksum_sha256,status)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values.get("context_assembly_id"),
                values["retrieval_run_id"],
                values.get("model_assignment_id"),
                values.get("scope", "admin_rag_lab"),
                values.get("session_id"),
                values["query_checksum_sha256"],
                values.get("status", "accepted"),
            ),
        )
        return public_id

    def grounded_request(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM rag_grounded_requests WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("grounded request not found")
        return row

    def record_grounded_answer(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_grounded_answers(public_id,grounded_request_id,answer_status,
            answer_checksum_sha256,answer_language,citation_count,stop_reason,
            runtime_milliseconds,role_token_leakage,prompt_leakage,unicode_valid)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["grounded_request_id"],
                values["answer_status"],
                values.get("answer_checksum_sha256"),
                values.get("answer_language", "unknown"),
                values.get("citation_count", 0),
                values.get("stop_reason"),
                values.get("runtime_milliseconds"),
                1 if values.get("role_token_leakage") else 0,
                1 if values.get("prompt_leakage") else 0,
                1 if values.get("unicode_valid", True) else 0,
            ),
        )
        return public_id

    def answer_for_request(
        self, connection: sqlite3.Connection, grounded_request_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM rag_grounded_answers WHERE grounded_request_id=? "
            "ORDER BY id DESC LIMIT 1",
            (grounded_request_id,),
        ).fetchone()

    # --- answer citations -----------------------------------------------------

    def record_citation(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_answer_citations(public_id,grounded_answer_id,citation_label,
            chunk_id,source_id,source_version_id,rank,content_checksum_sha256,validation_status)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["grounded_answer_id"],
                values["citation_label"],
                values.get("chunk_id"),
                values.get("source_id"),
                values.get("source_version_id"),
                values.get("rank"),
                values.get("content_checksum_sha256"),
                values.get("validation_status", "valid"),
            ),
        )
        return public_id

    def citations_for_answer(
        self, connection: sqlite3.Connection, grounded_answer_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_answer_citations WHERE grounded_answer_id=? ORDER BY rank",
            (grounded_answer_id,),
        ).fetchall()

    # --- grounding issues -----------------------------------------------------

    def record_issue(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_grounding_issues(public_id,grounded_request_id,issue_code,
            severity,message,details_json) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["grounded_request_id"],
                values["issue_code"],
                values["severity"],
                values.get("message", ""),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def issues_for_request(
        self, connection: sqlite3.Connection, grounded_request_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_grounding_issues WHERE grounded_request_id=? ORDER BY id",
            (grounded_request_id,),
        ).fetchall()

    # --- evaluation suites/fixtures/runs/metrics -----------------------------

    def create_evaluation_suite(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_evaluation_suites(public_id,knowledge_space_id,name,version,
            evaluation_type,configuration_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["knowledge_space_id"],
                values["name"],
                values["version"],
                values.get("evaluation_type", "both"),
                values.get("configuration_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def evaluation_suite(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM rag_evaluation_suites WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("evaluation suite not found")
        return row

    def list_evaluation_suites(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_evaluation_suites ORDER BY created_at DESC,id DESC"
        ).fetchall()

    def record_fixture(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_evaluation_fixtures(public_id,evaluation_suite_id,query,language,
            expected_relevant_chunk_ids_json,expected_relevant_source_ids_json,
            expected_no_answer,required_keywords_json,forbidden_claims_json,
            expected_answer_language,injection_test,severity,fixture_checksum_sha256)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["evaluation_suite_id"],
                values["query"],
                values.get("language", "unknown"),
                values.get("expected_relevant_chunk_ids_json", "[]"),
                values.get("expected_relevant_source_ids_json", "[]"),
                1 if values.get("expected_no_answer") else 0,
                values.get("required_keywords_json", "[]"),
                values.get("forbidden_claims_json", "[]"),
                values.get("expected_answer_language"),
                1 if values.get("injection_test") else 0,
                values.get("severity", "info"),
                values["fixture_checksum_sha256"],
            ),
        )
        return public_id

    def fixtures_for_suite(
        self, connection: sqlite3.Connection, suite_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_evaluation_fixtures WHERE evaluation_suite_id=? ORDER BY id",
            (suite_id,),
        ).fetchall()

    def create_evaluation_run(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_evaluation_runs(public_id,evaluation_suite_id,
            retrieval_profile_id,model_assignment_id,total_fixtures,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["evaluation_suite_id"],
                values.get("retrieval_profile_id"),
                values.get("model_assignment_id"),
                values.get("total_fixtures", 0),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def evaluation_run(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM rag_evaluation_runs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("evaluation run not found")
        return row

    def update_evaluation_run(
        self, connection: sqlite3.Connection, run_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE rag_evaluation_runs SET {columns} WHERE id=?", (*fields.values(), run_id)
        )

    def record_metric(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_evaluation_metrics(public_id,evaluation_run_id,metric_scope,
            metric_name,metric_value,sample_size,details_json) VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values["evaluation_run_id"],
                values["metric_scope"],
                values["metric_name"],
                values.get("metric_value"),
                values.get("sample_size", 0),
                values.get("details_json", "{}"),
            ),
        )
        return public_id

    def metrics_for_run(self, connection: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM rag_evaluation_metrics WHERE evaluation_run_id=? ORDER BY id",
            (run_id,),
        ).fetchall()

    # --- index comparisons -----------------------------------------------------

    def record_comparison(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_index_comparisons(public_id,left_vector_index_id,
            right_vector_index_id,left_keyword_index_id,right_keyword_index_id,
            evaluation_suite_id,compatibility,ranked,fields_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values.get("left_vector_index_id"),
                values.get("right_vector_index_id"),
                values.get("left_keyword_index_id"),
                values.get("right_keyword_index_id"),
                values.get("evaluation_suite_id"),
                values["compatibility"],
                1 if values.get("ranked") else 0,
                values.get("fields_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def comparison(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM rag_index_comparisons WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("index comparison not found")
        return row

    # --- manifests -----------------------------------------------------

    def record_manifest(
        self, connection: sqlite3.Connection, space_id: int, manifest_json: str, checksum: str
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO rag_manifests(public_id,knowledge_space_id,manifest_json,
            manifest_checksum_sha256) VALUES (?,?,?,?)""",
            (public_id, space_id, manifest_json, checksum),
        )
        return public_id

    def latest_manifest(
        self, connection: sqlite3.Connection, space_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM rag_manifests WHERE knowledge_space_id=? ORDER BY id DESC LIMIT 1",
            (space_id,),
        ).fetchone()
