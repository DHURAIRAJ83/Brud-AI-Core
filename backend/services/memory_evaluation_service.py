"""Phase 17 memory retrieval evaluation.

Measures memory retrieval independently from conversation orchestration
generation, using only fixtures with known relevant/excluded memory
IDs -- never fabricated relevance labels.
"""

from __future__ import annotations

import hashlib
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.conversation_memory import (
    ConversationMemoryRepository,
    public_row,
)
from backend.models.conversation_memory import (
    EvaluationFixtureCreate,
    EvaluationRunCreate,
    EvaluationSuiteCreate,
    MemoryRetrieveRequest,
)
from backend.services.memory_service import MemoryService
from core_model.conversation.evaluation import (
    aggregate_retrieval_metrics,
    exclusion_rate,
    hit_rate,
    mean_reciprocal_rank,
    ndcg_at_k,
    owner_filter_accuracy,
    precision_at_k,
    recall_at_k,
)
from core_model.conversation.manifest import (
    manifest_checksum,
    missing_required_fields,
    scan_for_sensitive_content,
    verify_manifest_checksum,
)

DEFAULT_K = 5


class MemoryEvaluationService:
    def __init__(
        self,
        repository: ConversationMemoryRepository,
        memory_service: MemoryService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.memory_service = memory_service
        self.settings = settings

    # --- suites -----------------------------------------------------

    def create_suite(self, payload: EvaluationSuiteCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_evaluation_suite(
                connection,
                {
                    "name": payload.name, "version": payload.version,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "memory_evaluation_suite_created", admin_id, public_id)
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
                "participant_scope_key": payload.participant_scope_key,
                "query": payload.query,
                "expected_retrieved_memory_ids": payload.expected_retrieved_memory_ids,
                "expected_excluded_memory_ids": payload.expected_excluded_memory_ids,
            }
            checksum = hashlib.sha256(dumps_json(checksum_payload).encode("utf-8")).hexdigest()
            public_id = self.repository.record_fixture(
                connection,
                {
                    "evaluation_suite_id": suite["id"],
                    "participant_scope_key": payload.participant_scope_key,
                    "session_mode": payload.session_mode,
                    "query": payload.query,
                    "query_language": payload.query_language,
                    "expected_retrieved_memory_ids_json": dumps_json(
                        payload.expected_retrieved_memory_ids
                    ),
                    "expected_excluded_memory_ids_json": dumps_json(
                        payload.expected_excluded_memory_ids
                    ),
                    "expected_language": payload.expected_language,
                    "expected_rag_use": payload.expected_rag_use,
                    "expected_no_memory_behavior": payload.expected_no_memory_behavior,
                    "expected_response_status": payload.expected_response_status,
                    "injection_test": payload.injection_test,
                    "severity": payload.severity,
                    "fixture_checksum_sha256": checksum,
                },
            )
            self._audit(connection, "memory_evaluation_fixture_added", admin_id, public_id)
            row = connection.execute(
                "SELECT * FROM memory_evaluation_fixtures WHERE public_id=?", (public_id,)
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
            public_id = self.repository.create_evaluation_run(
                connection,
                {
                    "evaluation_suite_id": suite["id"],
                    "retrieval_profile_id": profile_id,
                    "total_fixtures": len(fixtures),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "memory_evaluation_run_created", admin_id, public_id)
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
                "SELECT * FROM memory_evaluation_suites WHERE id=?", (run["evaluation_suite_id"],)
            ).fetchone()
            fixtures = self.repository.fixtures_for_suite(connection, suite["id"])
            profile_row = (
                connection.execute(
                    "SELECT public_id FROM memory_retrieval_profiles WHERE id=?",
                    (run["retrieval_profile_id"],),
                ).fetchone()
                if run["retrieval_profile_id"]
                else None
            )
            self.repository.update_evaluation_run(connection, run["id"], {"status": "running"})

        if not fixtures or profile_row is None:
            with self.repository.transaction() as connection:
                self.repository.update_evaluation_run(connection, run["id"], {"status": "failed"})
            raise ValidationError("evaluation run requires fixtures and a retrieval profile")

        per_fixture_results = []
        completed = 0
        for fixture in fixtures:
            expected_ids = set(_loads(fixture["expected_retrieved_memory_ids_json"]))
            excluded_ids = set(_loads(fixture["expected_excluded_memory_ids_json"]))
            retrieval = self.memory_service.retrieve(
                MemoryRetrieveRequest(
                    retrieval_profile_public_id=profile_row["public_id"],
                    participant_scope_key=fixture["participant_scope_key"],
                    query=fixture["query"],
                ),
                admin_id,
            )
            retrieved_ids = [entry["memory_item_public_id"] for entry in retrieval["results"]]
            with self.repository.transaction() as owner_connection:
                owned_rows = self.repository.list_memory_items(
                    owner_connection, participant_scope_key=fixture["participant_scope_key"]
                )
                owned_ids = {row["public_id"] for row in owned_rows}
            per_fixture_results.append(
                {
                    "recall_at_k": recall_at_k(retrieved_ids, expected_ids, DEFAULT_K),
                    "precision_at_k": precision_at_k(retrieved_ids, expected_ids, DEFAULT_K),
                    "mrr": mean_reciprocal_rank(retrieved_ids, expected_ids),
                    "ndcg_at_k": ndcg_at_k(retrieved_ids, expected_ids, DEFAULT_K),
                    "hit_rate": hit_rate(retrieved_ids, expected_ids),
                    "owner_filter_accuracy": owner_filter_accuracy(retrieved_ids, owned_ids),
                    "deleted_exclusion_rate": exclusion_rate(excluded_ids, set(retrieved_ids)),
                    "expired_exclusion_rate": exclusion_rate(excluded_ids, set(retrieved_ids)),
                    "revoked_exclusion_rate": exclusion_rate(excluded_ids, set(retrieved_ids)),
                    "conflict_detection_accuracy": None,
                    "language_preference_retrieval_accuracy": (
                        1.0
                        if not fixture["expected_language"]
                        or retrieval.get("query_language") == fixture["expected_language"]
                        else 0.0
                    ),
                    "latency_ms": retrieval.get("runtime_milliseconds"),
                }
            )
            completed += 1

        aggregated = aggregate_retrieval_metrics(per_fixture_results)

        with self.repository.transaction() as connection:
            for name, value in aggregated.items():
                if name == "sample_size":
                    continue
                self.repository.record_metric(
                    connection,
                    {
                        "evaluation_run_id": run["id"],
                        "metric_scope": "retrieval",
                        "metric_name": name,
                        "metric_value": value,
                        "sample_size": aggregated.get("sample_size", 0),
                    },
                )
            self.repository.update_evaluation_run(
                connection, run["id"], {"status": "completed", "completed_fixtures": completed}
            )
            connection.execute(
                "UPDATE memory_evaluation_runs SET completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (run["id"],),
            )
            self._audit(connection, "memory_evaluation_run_executed", admin_id, public_id)
            return public_row(self.repository.evaluation_run(connection, public_id))

    # --- manifest -----------------------------------------------------

    def generate_manifest(self, policy_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, policy_public_id)
            active_profiles = connection.execute(
                "SELECT public_id FROM memory_retrieval_profiles WHERE status='active' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            manifest = {
                "memory_policy_public_id": policy_public_id,
                "memory_policy_checksum": hashlib.sha256(
                    dumps_json(
                        {
                            "default_session_mode": policy["default_session_mode"],
                            "allow_long_term_memory": policy["allow_long_term_memory"],
                            "require_explicit_consent": policy["require_explicit_consent"],
                        }
                    ).encode("utf-8")
                ).hexdigest(),
                "session_mode_configuration": {
                    "default_session_mode": policy["default_session_mode"],
                    "maximum_session_turns": policy["maximum_session_turns"],
                    "maximum_session_age_seconds": policy["maximum_session_age_seconds"],
                },
                "summary_policy": {
                    "allow_session_summary": bool(policy["allow_session_summary"]),
                    "maximum_summary_tokens": policy["maximum_summary_tokens"],
                },
                "consent_policy": {
                    "require_explicit_consent": bool(policy["require_explicit_consent"]),
                },
                "allowed_memory_categories": _loads(policy["allowed_memory_categories_json"]),
                "forbidden_memory_categories": list(self.settings.memory_forbidden_categories_list),
                "memory_retrieval_profile": (
                    active_profiles["public_id"] if active_profiles else None
                ),
                "embedding_index_lineage": {},
                "rag_profile_lineage": {},
                "inference_assignment_version": None,
                "context_budget_configuration": {
                    "maximum_short_term_tokens": policy["maximum_short_term_tokens"],
                    "maximum_memory_tokens": self.settings.memory_max_context_tokens,
                },
                "evaluation_suite_checksum": None,
                "retrieval_metrics": {},
                "privacy_isolation_metrics": {},
                "known_limitations": [
                    "conversation memory retrieval does not guarantee factual correctness",
                    "keyword-only retrieval scoring is used when no embedding model is configured",
                    "conflict detection uses a bounded, deterministic heuristic, "
                    "not semantic judgment",
                ],
                "software_versions": {"phase": 17},
                "created_at": None,
            }
            concerns = scan_for_sensitive_content(manifest)
            if concerns:
                raise ValidationError(f"manifest failed sensitive-content scan: {concerns}")
            missing = missing_required_fields(manifest)
            checksum = manifest_checksum(manifest)
            manifest_public_id = self.repository.record_manifest(
                connection, policy["id"], dumps_json(manifest), checksum
            )
            self._audit(
                connection, "conversation_memory_manifest_generated", admin_id,
                policy_public_id, missing_fields=missing,
            )
            row = connection.execute(
                "SELECT * FROM conversation_memory_manifests WHERE public_id=?",
                (manifest_public_id,),
            ).fetchone()
            return public_row(row)

    def verify_manifest(self, policy_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            policy = self.repository.policy(connection, policy_public_id)
            row = self.repository.latest_manifest(connection, policy["id"])
            if not row:
                raise ValidationError("no manifest recorded for this memory policy")
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
                "conversation_memory", resource_id, "success", dumps_json(metadata),
            ),
        )


def _loads(value: str | None) -> list[Any]:
    if not value:
        return []
    return loads_json(value)
