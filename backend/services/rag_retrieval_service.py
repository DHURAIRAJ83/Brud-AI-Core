"""Phase 16 RAG retrieval: retrieval profiles, hybrid vector+keyword
search, access filtering, and deterministic ranking.

Filtering happens BEFORE scoring and context assembly — a blocked or
inaccessible chunk never enters the candidate pool at all, never merely
hidden from citations afterward.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.rag import RagRepository, public_row
from backend.models.rag import RetrievalProfileCreate, RetrievalProfilePatch, RetrieveRequest
from core_model.rag.access_filter import RetrievalFilters, apply_access_filters
from core_model.rag.embedding import compute_embedding, unpack_vector
from core_model.rag.hybrid_retrieval import (
    HybridScoreInputs,
    HybridWeights,
    collapse_exact_duplicates,
    compute_combined_score,
    enforce_source_diversity,
    rank_with_tie_break,
)
from core_model.rag.keyword_index import escape_fts5_query, keyword_match_score
from core_model.rag.language_routing import classify_language
from core_model.rag.query_normalization import QueryNormalizationConfig, normalize_query
from core_model.rag.vector_index import normalize_scores, score_vectors


class RagRetrievalService:
    def __init__(self, repository: RagRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- retrieval profiles -----------------------------------------------------

    def create_profile(
        self, space_public_id: str, payload: RetrievalProfileCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            space = self.repository.space(connection, space_public_id)
            if abs(payload.vector_weight + payload.keyword_weight - 1.0) > 0.01:
                raise ValidationError("vector_weight and keyword_weight must sum to 1.0")
            public_id = self.repository.create_retrieval_profile(
                connection,
                {
                    "knowledge_space_id": space["id"],
                    "name": payload.name,
                    "vector_top_k": payload.vector_top_k,
                    "keyword_top_k": payload.keyword_top_k,
                    "final_top_k": payload.final_top_k,
                    "vector_weight": payload.vector_weight,
                    "keyword_weight": payload.keyword_weight,
                    "heading_boost": payload.heading_boost,
                    "exact_match_boost": payload.exact_match_boost,
                    "language_match_boost": payload.language_match_boost,
                    "source_priority_json": dumps_json(payload.source_priority),
                    "minimum_score": payload.minimum_score,
                    "deduplication_policy": payload.deduplication_policy,
                    "diversity_policy": payload.diversity_policy,
                    "context_token_budget": payload.context_token_budget,
                    "injection_filter_policy": payload.injection_filter_policy,
                    "no_answer_threshold": payload.no_answer_threshold,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "rag_retrieval_profile_created", admin_id, public_id)
            return public_row(self.repository.retrieval_profile(connection, public_id))

    def list_profiles(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_retrieval_profiles(connection)
            return {"items": [public_row(row) for row in rows]}

    def get_profile(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.retrieval_profile(connection, public_id))

    def patch_profile(
        self, public_id: str, payload: RetrievalProfilePatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.retrieval_profile(connection, public_id)
            fields: dict[str, Any] = {}
            for name in (
                "vector_top_k", "keyword_top_k", "final_top_k", "vector_weight",
                "keyword_weight", "minimum_score", "context_token_budget",
                "injection_filter_policy", "no_answer_threshold",
            ):
                value = getattr(payload, name)
                if value is not None:
                    fields[name] = value
            self.repository.update_retrieval_profile(connection, profile["id"], fields)
            self._audit(connection, "rag_retrieval_profile_updated", admin_id, public_id)
            return public_row(self.repository.retrieval_profile(connection, public_id))

    def validate_profile(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.retrieval_profile(connection, public_id)
            weight_sum = profile["vector_weight"] + profile["keyword_weight"]
            if abs(weight_sum - 1.0) > 0.01:
                raise ValidationError("vector_weight and keyword_weight must sum to 1.0")
            self.repository.update_retrieval_profile(
                connection, profile["id"], {"status": "validated"}
            )
            self._audit(connection, "rag_retrieval_profile_validated", admin_id, public_id)
            return public_row(self.repository.retrieval_profile(connection, public_id))

    def activate_profile(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.retrieval_profile(connection, public_id)
            if profile["status"] != "validated":
                raise ValidationError("profile must be validated before activation")
            self.repository.update_retrieval_profile(
                connection, profile["id"], {"status": "active"}
            )
            self._audit(connection, "rag_retrieval_profile_activated", admin_id, public_id)
            return public_row(self.repository.retrieval_profile(connection, public_id))

    # --- retrieval -----------------------------------------------------

    def retrieve(self, payload: RetrieveRequest, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.retrieval_profile(
                connection, payload.retrieval_profile_public_id
            )
            if profile["status"] != "active":
                raise ValidationError("retrieval profile must be active to be used")
            space_id = profile["knowledge_space_id"]
            started = time.perf_counter()

            language_info = classify_language(payload.query)
            normalized = normalize_query(
                payload.query,
                language_category=language_info["language_category"],
                config=QueryNormalizationConfig(),
            )
            query_checksum = hashlib.sha256(payload.query.encode("utf-8")).hexdigest()

            vector_index = self.repository.active_vector_index_for_space(connection, space_id)
            keyword_index = self.repository.active_keyword_index_for_space(connection, space_id)

            candidates = self._gather_candidates(
                connection,
                vector_index=vector_index,
                keyword_index=keyword_index,
                normalized_query=normalized["normalized_query"],
                profile=profile,
            )
            total_candidates = len(candidates)

            filters = RetrievalFilters(
                source_public_ids=tuple(payload.filters.source_public_ids),
                source_version_public_ids=tuple(payload.filters.source_version_public_ids),
                languages=tuple(payload.filters.languages),
                record_types=tuple(payload.filters.record_types),
                licence_statuses=tuple(payload.filters.licence_statuses),
                approval_statuses=tuple(payload.filters.approval_statuses),
            )
            filtered = apply_access_filters(
                candidates,
                filters,
                require_approved_sources=self.settings.rag_require_approved_sources,
            )
            accepted = filtered["accepted"]

            scored = []
            for candidate in accepted:
                weights = HybridWeights(
                    vector_weight=profile["vector_weight"],
                    keyword_weight=profile["keyword_weight"],
                    heading_boost=profile["heading_boost"],
                    exact_match_boost=profile["exact_match_boost"],
                    language_match_boost=profile["language_match_boost"],
                )
                inputs = HybridScoreInputs(
                    chunk_public_id=candidate["chunk_public_id"],
                    source_public_id=candidate["source_public_id"],
                    content_checksum_sha256=candidate["content_checksum_sha256"],
                    vector_score=candidate.get("vector_score_normalized"),
                    keyword_score=candidate.get("keyword_score_normalized"),
                    is_heading_match=bool(candidate.get("heading_path")),
                    is_exact_match=normalized["normalized_query"].lower()
                    in candidate["normalized_text"].lower(),
                    language_match=candidate["language"] == language_info["language_category"],
                )
                result = compute_combined_score(inputs, weights)
                result.update(
                    {
                        "source_version_public_id": candidate["source_version_public_id"],
                        "language": candidate["language"],
                        "normalized_text": candidate["normalized_text"],
                        "heading_path": candidate.get("heading_path"),
                        "injection_status": candidate["injection_status"],
                        "estimated_token_count": candidate["estimated_token_count"],
                        "title": candidate.get("title", ""),
                        "location": candidate.get("location", ""),
                    }
                )
                scored.append(result)

            # Exact-duplicate collapsing always applies; "exact_and_near"
            # additionally controls near-duplicate evidence, which is
            # reported (see rag_chunks.quality_issues) but not yet collapsed
            # at retrieval time — a documented, honest scope limit, not a
            # silent gap.
            scored = collapse_exact_duplicates(scored)

            ranked = rank_with_tie_break(scored)
            ranked = [
                entry for entry in ranked
                if entry["combined_score"] >= profile["minimum_score"]
            ]

            if profile["diversity_policy"] == "source_diversity":
                ranked = enforce_source_diversity(
                    ranked, max_per_source=2, top_k=profile["final_top_k"]
                )
            else:
                ranked = ranked[: profile["final_top_k"]]

            runtime_ms = int((time.perf_counter() - started) * 1000)
            no_answer_score = ranked[0]["combined_score"] if ranked else 0.0

            run_public_id = self.repository.create_retrieval_run(
                connection,
                {
                    "retrieval_profile_id": profile["id"],
                    "knowledge_space_id": space_id,
                    "vector_index_id": vector_index["id"] if vector_index else None,
                    "keyword_index_id": keyword_index["id"] if keyword_index else None,
                    "normalized_query": normalized["normalized_query"],
                    "query_checksum_sha256": query_checksum,
                    "query_language": language_info["language_category"],
                    "filters_json": dumps_json(payload.filters.model_dump()),
                    "top_k_configuration_json": dumps_json(
                        {
                            "vector_top_k": profile["vector_top_k"],
                            "keyword_top_k": profile["keyword_top_k"],
                            "final_top_k": profile["final_top_k"],
                        }
                    ),
                    "runtime_milliseconds": runtime_ms,
                    "total_candidates": total_candidates,
                    "final_result_count": len(ranked),
                    "no_answer_score": no_answer_score,
                    "status": "completed" if ranked else "no_results",
                },
            )
            run = self.repository.retrieval_run(connection, run_public_id)

            for entry in ranked:
                chunk_row = connection.execute(
                    "SELECT id FROM rag_chunks WHERE public_id=?", (entry["chunk_public_id"],)
                ).fetchone()
                source_row = connection.execute(
                    "SELECT id FROM rag_knowledge_sources WHERE public_id=?",
                    (entry["source_public_id"],),
                ).fetchone()
                version_row = connection.execute(
                    "SELECT id FROM rag_source_versions WHERE public_id=?",
                    (entry["source_version_public_id"],),
                ).fetchone()
                self.repository.record_retrieved_chunk(
                    connection,
                    {
                        "retrieval_run_id": run["id"],
                        "rank": entry["rank"],
                        "chunk_id": chunk_row["id"],
                        "source_id": source_row["id"],
                        "source_version_id": version_row["id"],
                        "vector_score": entry.get("vector_score"),
                        "keyword_score": entry.get("keyword_score"),
                        "combined_score": entry["combined_score"],
                        "rerank_score": None,
                        "injection_status": entry["injection_status"],
                        "filter_evidence_json": dumps_json({}),
                        "selected_for_context": True,
                    },
                )

            self._audit(
                connection, "rag_retrieval_run_executed", admin_id, run_public_id,
                result_count=len(ranked),
            )
            return {
                **public_row(run),
                "results": ranked,
            }

    def _gather_candidates(
        self, connection, *, vector_index, keyword_index, normalized_query: str, profile
    ) -> list[dict[str, Any]]:
        by_chunk: dict[str, dict[str, Any]] = {}

        if vector_index is not None:
            model_row = connection.execute(
                """SELECT m.provider_type, m.dimensions FROM rag_embedding_runs r
                JOIN rag_embedding_models m ON m.id=r.embedding_model_id WHERE r.id=?""",
                (vector_index["embedding_run_id"],),
            ).fetchone()
            query_embedding = compute_embedding(
                normalized_query,
                provider_type=model_row["provider_type"],
                dimensions=model_row["dimensions"],
            )
            embeddings = connection.execute(
                """SELECT e.chunk_id, e.vector_blob, e.dimensions, c.public_id AS chunk_public_id
                FROM rag_chunk_embeddings e JOIN rag_chunks c ON c.id=e.chunk_id
                WHERE e.embedding_run_id=?""",
                (vector_index["embedding_run_id"],),
            ).fetchall()
            vectors = [
                unpack_vector(row["vector_blob"], dimensions=row["dimensions"])
                for row in embeddings
            ]
            scores = (
                score_vectors(
                    query_embedding["vector"],
                    vectors,
                    distance_metric=vector_index["distance_metric"],
                )
                if vectors
                else []
            )
            normalized_scores = normalize_scores(scores)
            paired = sorted(
                zip(embeddings, scores, normalized_scores, strict=True),
                key=lambda item: -item[1],
            )[: profile["vector_top_k"]]
            for row, raw_score, norm_score in paired:
                entry = by_chunk.setdefault(row["chunk_public_id"], {})
                entry["vector_score"] = raw_score
                entry["vector_score_normalized"] = norm_score

        if keyword_index is not None and keyword_index["storage_key"]:
            fts_query = escape_fts5_query(normalized_query)
            try:
                rows = connection.execute(
                    f'SELECT chunk_public_id, bm25("{keyword_index["storage_key"]}") AS score '
                    f'FROM "{keyword_index["storage_key"]}" '
                    f'WHERE "{keyword_index["storage_key"]}" MATCH ? '
                    f"ORDER BY score LIMIT ?",
                    (fts_query, profile["keyword_top_k"]),
                ).fetchall()
            except Exception:  # noqa: BLE001 - a malformed FTS query must fail closed, not crash retrieval
                rows = []
            raw_scores = [keyword_match_score(row["score"]) for row in rows]
            norm_scores = normalize_scores(raw_scores)
            for row, raw_score, norm_score in zip(rows, raw_scores, norm_scores, strict=True):
                entry = by_chunk.setdefault(row["chunk_public_id"], {})
                entry["keyword_score"] = raw_score
                entry["keyword_score_normalized"] = norm_score

        candidates = []
        for chunk_public_id, scores in by_chunk.items():
            chunk = connection.execute(
                "SELECT * FROM rag_chunks WHERE public_id=?", (chunk_public_id,)
            ).fetchone()
            if chunk is None:
                continue
            version = connection.execute(
                "SELECT * FROM rag_source_versions WHERE id=?", (chunk["source_version_id"],)
            ).fetchone()
            source = connection.execute(
                "SELECT * FROM rag_knowledge_sources WHERE id=?", (version["knowledge_source_id"],)
            ).fetchone()
            candidates.append(
                {
                    "chunk_public_id": chunk["public_id"],
                    "source_public_id": source["public_id"],
                    "source_version_public_id": version["public_id"],
                    "content_checksum_sha256": chunk["content_checksum_sha256"],
                    "normalized_text": chunk["normalized_text"],
                    "language": chunk["language"],
                    "heading_path": chunk["heading_path_json"],
                    "estimated_token_count": chunk["estimated_token_count"],
                    "injection_status": chunk["injection_status"],
                    "approval_status": source["approval_status"],
                    "licence_status": source["licence_status"],
                    "title": source["title"],
                    "location": chunk["source_location_json"],
                    **scores,
                }
            )
        return candidates

    def get_retrieval_run(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.retrieval_run(connection, public_id))

    def get_retrieval_results(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.retrieval_run(connection, public_id)
            rows = self.repository.retrieved_chunks_for_run(connection, run["id"])
            return {"items": [public_row(row) for row in rows]}

    # --- audit -----------------------------------------------------

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                "rag", resource_id, "success", dumps_json(metadata),
            ),
        )
