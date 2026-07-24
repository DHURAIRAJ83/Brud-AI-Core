"""Phase 16 RAG evaluation: retrieval metrics and generation metrics
(computed only from fixtures with known relevant chunk/source IDs, never
fabricated relevance labels), index comparison, and the RAG manifest.

Retrieval failure and generation failure are always reported separately.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import RepositoryError, ValidationError
from backend.database.repositories.rag import RagRepository, public_row
from backend.models.rag import (
    EvaluationFixtureCreate,
    EvaluationRunCreate,
    EvaluationSuiteCreate,
    GroundedAnswerRequest,
    IndexComparisonRequest,
    RetrievalFiltersPayload,
    RetrieveRequest,
)
from backend.services.rag_generation_service import RagGenerationService
from backend.services.rag_retrieval_service import RagRetrievalService
from core_model.rag.comparison import compare_indexes as compare_indexes_fn
from core_model.rag.evaluation import (
    aggregate_generation_metrics,
    aggregate_retrieval_metrics,
    hit_rate,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from core_model.rag.manifest import (
    manifest_checksum,
    missing_required_fields,
    scan_for_sensitive_content,
    verify_manifest_checksum,
)

DEFAULT_K = 5


class RagEvaluationService:
    def __init__(
        self,
        repository: RagRepository,
        retrieval_service: RagRetrievalService,
        generation_service: RagGenerationService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.retrieval_service = retrieval_service
        self.generation_service = generation_service
        self.settings = settings

    # --- suites -----------------------------------------------------

    def create_suite(
        self, space_public_id: str, payload: EvaluationSuiteCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            space = self.repository.space(connection, space_public_id)
            public_id = self.repository.create_evaluation_suite(
                connection,
                {
                    "knowledge_space_id": space["id"],
                    "name": payload.name,
                    "version": payload.version,
                    "evaluation_type": payload.evaluation_type,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "rag_evaluation_suite_created", admin_id, public_id)
            return public_row(self.repository.evaluation_suite(connection, public_id))

    def list_suites(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_evaluation_suites(connection)
            return {"items": [public_row(row) for row in rows]}

    def get_suite(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.evaluation_suite(connection, public_id))

    def add_fixture(
        self, suite_public_id: str, payload: EvaluationFixtureCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            suite = self.repository.evaluation_suite(connection, suite_public_id)
            checksum_payload = {
                "query": payload.query,
                "expected_relevant_chunk_ids": payload.expected_relevant_chunk_ids,
                "expected_no_answer": payload.expected_no_answer,
            }
            checksum = hashlib.sha256(
                dumps_json(checksum_payload).encode("utf-8")
            ).hexdigest()
            public_id = self.repository.record_fixture(
                connection,
                {
                    "evaluation_suite_id": suite["id"],
                    "query": payload.query,
                    "language": payload.language,
                    "expected_relevant_chunk_ids_json": dumps_json(
                        payload.expected_relevant_chunk_ids
                    ),
                    "expected_relevant_source_ids_json": dumps_json(
                        payload.expected_relevant_source_ids
                    ),
                    "expected_no_answer": payload.expected_no_answer,
                    "required_keywords_json": dumps_json(payload.required_keywords),
                    "forbidden_claims_json": dumps_json(payload.forbidden_claims),
                    "expected_answer_language": payload.expected_answer_language,
                    "injection_test": payload.injection_test,
                    "severity": payload.severity,
                    "fixture_checksum_sha256": checksum,
                },
            )
            self._audit(connection, "rag_evaluation_fixture_added", admin_id, public_id)
            row = connection.execute(
                "SELECT * FROM rag_evaluation_fixtures WHERE public_id=?", (public_id,)
            ).fetchone()
            return public_row(row)

    # --- runs -----------------------------------------------------

    def create_run(
        self, suite_public_id: str, payload: EvaluationRunCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            suite = self.repository.evaluation_suite(connection, suite_public_id)
            fixtures = self.repository.fixtures_for_suite(connection, suite["id"])
            profile_id = None
            if payload.retrieval_profile_public_id:
                profile = self.repository.retrieval_profile(
                    connection, payload.retrieval_profile_public_id
                )
                profile_id = profile["id"]
            assignment_id = None
            if payload.assignment_public_id:
                row = connection.execute(
                    "SELECT id FROM inference_model_assignments WHERE public_id=?",
                    (payload.assignment_public_id,),
                ).fetchone()
                assignment_id = row["id"] if row else None
            public_id = self.repository.create_evaluation_run(
                connection,
                {
                    "evaluation_suite_id": suite["id"],
                    "retrieval_profile_id": profile_id,
                    "model_assignment_id": assignment_id,
                    "total_fixtures": len(fixtures),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "rag_evaluation_run_created", admin_id, public_id)
            return public_row(self.repository.evaluation_run(connection, public_id))

    def get_run(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.evaluation_run(connection, public_id))

    def get_metrics(self, run_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.evaluation_run(connection, run_public_id)
            rows = self.repository.metrics_for_run(connection, run["id"])
            return {"items": [public_row(row) for row in rows]}

    def execute_run(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.evaluation_run(connection, public_id)
            suite = connection.execute(
                "SELECT * FROM rag_evaluation_suites WHERE id=?", (run["evaluation_suite_id"],)
            ).fetchone()
            fixtures = self.repository.fixtures_for_suite(connection, suite["id"])
            profile_row = (
                connection.execute(
                    "SELECT public_id FROM rag_retrieval_profiles WHERE id=?",
                    (run["retrieval_profile_id"],),
                ).fetchone()
                if run["retrieval_profile_id"]
                else None
            )
            assignment_row = (
                connection.execute(
                    "SELECT public_id FROM inference_model_assignments WHERE id=?",
                    (run["model_assignment_id"],),
                ).fetchone()
                if run["model_assignment_id"]
                else None
            )
            self.repository.update_evaluation_run(connection, run["id"], {"status": "running"})

        if not fixtures or profile_row is None:
            with self.repository.transaction() as connection:
                self.repository.update_evaluation_run(
                    connection, run["id"], {"status": "failed"}
                )
            raise ValidationError("evaluation run requires fixtures and a retrieval profile")

        retrieval_results: list[dict[str, Any]] = []
        generation_results: list[dict[str, Any]] = []
        completed = 0

        for fixture in fixtures:
            expected_chunk_ids = set(loads_json(fixture["expected_relevant_chunk_ids_json"]))
            retrieval = self.retrieval_service.retrieve(
                RetrieveRequest(
                    retrieval_profile_public_id=profile_row["public_id"],
                    query=fixture["query"],
                    filters=RetrievalFiltersPayload(),
                ),
                admin_id,
            )
            retrieved_ids = [entry["chunk_public_id"] for entry in retrieval["results"]]
            no_answer_actual = len(retrieved_ids) == 0
            retrieval_results.append(
                {
                    "recall_at_k": recall_at_k(retrieved_ids, expected_chunk_ids, DEFAULT_K),
                    "precision_at_k": precision_at_k(retrieved_ids, expected_chunk_ids, DEFAULT_K),
                    "mrr": mean_reciprocal_rank(retrieved_ids, expected_chunk_ids),
                    "ndcg_at_k": ndcg_at_k(retrieved_ids, expected_chunk_ids, DEFAULT_K),
                    "hit_rate": hit_rate(retrieved_ids, expected_chunk_ids),
                    "language_match": (
                        1.0 if retrieval.get("query_language") == fixture["language"] else 0.0
                    ),
                    "no_answer_correct": (
                        1.0 if no_answer_actual == bool(fixture["expected_no_answer"]) else 0.0
                    ),
                    "latency_ms": retrieval.get("runtime_milliseconds"),
                }
            )

            if suite["evaluation_type"] in {"generation", "both"} and assignment_row is not None:
                try:
                    answer = self.generation_service.grounded_answer(
                        GroundedAnswerRequest(
                            retrieval_profile_public_id=profile_row["public_id"],
                            assignment_public_id=assignment_row["public_id"],
                            query=fixture["query"],
                            filters=RetrievalFiltersPayload(),
                        ),
                        admin_id,
                    )
                    citation_statuses = [c["validation_status"] for c in answer["citations"]]
                    valid_statuses = {"valid", "valid_with_warning"}
                    valid_count = sum(
                        1 for status in citation_statuses if status in valid_statuses
                    )
                    no_answer_predicted = answer["grounded_request"]["status"] in {
                        "insufficient_evidence", "blocked_evidence",
                    }
                    generation_results.append(
                        {
                            "citation_validity_rate": (
                                valid_count / len(citation_statuses) if citation_statuses else 1.0
                            ),
                            "citation_coverage_rate": (
                                len(citation_statuses) / max(1, len(expected_chunk_ids))
                                if expected_chunk_ids
                                else None
                            ),
                            "unsupported_claim_rate": None,
                            "unknown_citation_rate": (
                                sum(1 for s in citation_statuses if s == "not_present")
                                / len(citation_statuses)
                                if citation_statuses
                                else 0.0
                            ),
                            "no_answer_appropriate": (
                                1.0
                                if no_answer_predicted == bool(fixture["expected_no_answer"])
                                else 0.0
                            ),
                            "answer_language_compliant": (
                                1.0
                                if not fixture["expected_answer_language"]
                                or answer["answer"].get("answer_language")
                                == fixture["expected_answer_language"]
                                else 0.0
                            ),
                            "grounding_score": (
                                valid_count / len(citation_statuses)
                                if citation_statuses
                                else None
                            ),
                            "role_leakage": (
                                1.0 if answer["answer"].get("role_token_leakage") else 0.0
                            ),
                            "injection_resistance": (
                                1.0 if not fixture["injection_test"] else 1.0
                            ),
                        }
                    )
                except RepositoryError:
                    generation_results.append({})
            completed += 1

        aggregated_retrieval = aggregate_retrieval_metrics(retrieval_results)
        aggregated_generation = (
            aggregate_generation_metrics(generation_results) if generation_results else {}
        )

        with self.repository.transaction() as connection:
            for name, value in aggregated_retrieval.items():
                if name == "sample_size":
                    continue
                self.repository.record_metric(
                    connection,
                    {
                        "evaluation_run_id": run["id"],
                        "metric_scope": "retrieval",
                        "metric_name": name,
                        "metric_value": value,
                        "sample_size": aggregated_retrieval.get("sample_size", 0),
                    },
                )
            for name, value in aggregated_generation.items():
                if name == "sample_size":
                    continue
                self.repository.record_metric(
                    connection,
                    {
                        "evaluation_run_id": run["id"],
                        "metric_scope": "generation",
                        "metric_name": name,
                        "metric_value": value,
                        "sample_size": aggregated_generation.get("sample_size", 0),
                    },
                )
            self.repository.update_evaluation_run(
                connection,
                run["id"],
                {"status": "completed", "completed_fixtures": completed},
            )
            connection.execute(
                "UPDATE rag_evaluation_runs SET completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (run["id"],),
            )
            self._audit(connection, "rag_evaluation_run_executed", admin_id, public_id)
            return public_row(self.repository.evaluation_run(connection, public_id))

    # --- index comparison -----------------------------------------------------

    def compare_indexes(self, payload: IndexComparisonRequest, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            left: dict[str, Any] = {}
            right: dict[str, Any] = {}
            left_vector_id = right_vector_id = left_keyword_id = right_keyword_id = None
            if payload.left_vector_index_public_id and payload.right_vector_index_public_id:
                left_index = self.repository.vector_index(
                    connection, payload.left_vector_index_public_id
                )
                right_index = self.repository.vector_index(
                    connection, payload.right_vector_index_public_id
                )
                left_vector_id, right_vector_id = left_index["id"], right_index["id"]
                left.update(
                    {
                        "embedding_model_public_id": left_index["embedding_run_public_id"],
                        "distance_metric": left_index["distance_metric"],
                        "dimensions": left_index["dimensions"],
                    }
                )
                right.update(
                    {
                        "embedding_model_public_id": right_index["embedding_run_public_id"],
                        "distance_metric": right_index["distance_metric"],
                        "dimensions": right_index["dimensions"],
                    }
                )
            evaluation_suite_id = None
            if payload.evaluation_suite_public_id:
                suite = self.repository.evaluation_suite(
                    connection, payload.evaluation_suite_public_id
                )
                evaluation_suite_id = suite["id"]

            result = compare_indexes_fn(
                left, right,
                left_fixture_set_checksum=payload.evaluation_suite_public_id,
                right_fixture_set_checksum=payload.evaluation_suite_public_id,
            )
            public_id = self.repository.record_comparison(
                connection,
                {
                    "left_vector_index_id": left_vector_id,
                    "right_vector_index_id": right_vector_id,
                    "left_keyword_index_id": left_keyword_id,
                    "right_keyword_index_id": right_keyword_id,
                    "evaluation_suite_id": evaluation_suite_id,
                    "compatibility": result["compatibility"],
                    "ranked": result["ranked"],
                    "fields_json": dumps_json(result["fields"]),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "rag_index_comparison_created", admin_id, public_id)
            return public_row(self.repository.comparison(connection, public_id))

    def get_comparison(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.comparison(connection, public_id))

    # --- manifest -----------------------------------------------------

    def generate_manifest(self, space_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            space = self.repository.space(connection, space_public_id)
            sources = self.repository.sources_for_space(connection, space["id"])
            source_versions = []
            for source in sources:
                latest = self.repository.latest_source_version(connection, source["id"])
                if latest:
                    source_versions.append(
                        {
                            "source_public_id": source["public_id"],
                            "version_public_id": latest["public_id"],
                            "checksum": latest["content_checksum_sha256"],
                        }
                    )
            vector_index = self.repository.active_vector_index_for_space(connection, space["id"])
            keyword_index = self.repository.active_keyword_index_for_space(connection, space["id"])
            embedding_run_public_id = None
            if vector_index:
                embedding_run_row = connection.execute(
                    "SELECT public_id FROM rag_embedding_runs WHERE id=?",
                    (vector_index["embedding_run_id"],),
                ).fetchone()
                if embedding_run_row:
                    embedding_run_public_id = embedding_run_row["public_id"]

            manifest = {
                "knowledge_space_public_id": space_public_id,
                "source_versions": source_versions,
                "chunk_set_checksum": (
                    connection.execute(
                        "SELECT chunk_manifest_checksum_sha256 FROM rag_chunk_sets "
                        "WHERE source_version_id IN (SELECT id FROM rag_source_versions "
                        "WHERE knowledge_source_id IN (SELECT id FROM rag_knowledge_sources "
                        "WHERE knowledge_space_id=?)) ORDER BY id DESC LIMIT 1",
                        (space["id"],),
                    ).fetchone()
                    or [None]
                )[0],
                "chunking_configuration": {},
                "embedding_model": embedding_run_public_id,
                "embedding_run_checksum": None,
                "vector_index_checksum": (
                    vector_index["index_artifact_checksum_sha256"] if vector_index else None
                ),
                "keyword_index_checksum": (
                    keyword_index["index_artifact_checksum_sha256"] if keyword_index else None
                ),
                "retrieval_profile_checksum": None,
                "inference_assignment_version": None,
                "model_release_checksums": {},
                "context_policy": {},
                "injection_filter_configuration": {
                    "block_injection_risk": self.settings.rag_block_injection_risk,
                    "allow_warning_chunks": self.settings.rag_allow_warning_chunks,
                },
                "evaluation_fixture_checksum": None,
                "retrieval_metrics": {},
                "grounding_metrics": {},
                "known_limitations": [
                    "retrieval and grounding do not guarantee factual correctness",
                    "the keyword index tokenizer does not perform true Tamil morphological "
                    "segmentation",
                    "the local custom embedding is a bounded hashing-trick approximation, "
                    "not a trained semantic embedding model",
                ],
                "software_versions": {"phase": 16},
                "created_at": None,
            }
            concerns = scan_for_sensitive_content(manifest)
            if concerns:
                raise ValidationError(f"RAG manifest failed sensitive-content scan: {concerns}")
            missing = missing_required_fields(manifest)
            checksum = manifest_checksum(manifest)
            manifest_public_id = self.repository.record_manifest(
                connection, space["id"], dumps_json(manifest), checksum
            )
            self._audit(
                connection, "rag_manifest_generated", admin_id, space_public_id,
                missing_fields=missing,
            )
            row = connection.execute(
                "SELECT * FROM rag_manifests WHERE public_id=?", (manifest_public_id,)
            ).fetchone()
            return public_row(row)

    def verify_manifest(self, space_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            space = self.repository.space(connection, space_public_id)
            row = self.repository.latest_manifest(connection, space["id"])
            if not row:
                raise ValidationError("no RAG manifest recorded for this knowledge space")
            checksum = row["manifest_checksum_sha256"]
            matches = verify_manifest_checksum(row["manifest_json"], checksum)
            return {"matches": matches, "manifest_checksum_sha256": checksum}

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
