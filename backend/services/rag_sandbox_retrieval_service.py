"""Phase 13 Step 11/12 retrieval-configuration comparison and honest
retrieval evaluation.

Reuses `RagRetrievalService.retrieve()` verbatim for every query in a
finalized query set, against one sandbox index's own retrieval
profile. Metrics are computed only from `core_model.rag.evaluation`'s
pure functions and only when a query carries `expected_source_ids` --
otherwise the result is honestly marked `not_available`, never
fabricated. See docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import loads_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.rag import RagRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.rag import RetrievalFiltersPayload, RetrieveRequest
from backend.services.rag_retrieval_service import RagRetrievalService
from backend.services.rag_sandbox_eligibility_service import RagSandboxError
from core_model.rag.evaluation import (
    hit_rate,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)
from core_model.rag.language_routing import classify_language
from core_model.rag_sandbox import LANGUAGE_CATEGORY_TO_SANDBOX_LANGUAGE

logger = logging.getLogger(__name__)


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"rag_sandbox_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="rag_sandbox_experiment",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("rag_sandbox_audit_write_failed", extra={"action": action})


class RagSandboxRetrievalService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._rag_repository = RagRepository(settings.resolved_database_path)
        self._retrieval = RagRetrievalService(self._rag_repository, settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _retrieval_profile_public_id(self, retrieval_profile_id: int) -> str:
        with sqlite3.connect(self.settings.resolved_database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT public_id FROM rag_retrieval_profiles WHERE id=?",
                (retrieval_profile_id,),
            ).fetchone()
        if not row:
            raise RagSandboxError("this sandbox index has no active retrieval profile")
        return row["public_id"]

    def run_retrieval(
        self,
        experiment_public_id: str,
        *,
        index_public_id: str,
        query_set_public_id: str,
        admin_id: str,
    ) -> dict[str, Any]:
        index_row = self._sandbox.get_index(index_public_id)
        if index_row["status"] != "active":
            raise RagSandboxError("the sandbox index must be active before retrieval can run")
        query_set = self._sandbox.get_query_set(query_set_public_id)
        if query_set["status"] != "finalized":
            raise RagSandboxError("the query set must be finalized before retrieval can run")
        queries = self._sandbox.list_queries(query_set_public_id)
        if not queries:
            raise RagSandboxError("the query set has no queries")

        retrieval_profile_public_id = self._retrieval_profile_public_id(
            index_row["retrieval_profile_id"]
        )

        self._sandbox.update_experiment(
            experiment_public_id,
            {"status": "running_retrieval", "current_stage": "retrieval_evaluation"},
        )

        run = self._sandbox.record_retrieval_run(
            experiment_public_id,
            {
                "index_public_id": index_public_id,
                "query_set_public_id": query_set_public_id,
                "config_label": index_row["index_kind"],
                "total_queries": len(queries),
                "performed_by_admin_public_id": admin_id,
            },
        )

        for query in queries:
            retrieval_result = self._retrieval.retrieve(
                RetrieveRequest(
                    retrieval_profile_public_id=retrieval_profile_public_id,
                    query=query["query_text"],
                    filters=RetrievalFiltersPayload(approval_statuses=["approved"]),
                ),
                admin_id,
            )
            results = retrieval_result["results"]
            retrieved_record_ids = []
            for entry in results:
                heading_path = entry.get("heading_path")
                if isinstance(heading_path, str):
                    heading_path = loads_json(heading_path)
                if heading_path:
                    retrieved_record_ids.append(heading_path[0])
            duplicate_result_rate = (
                1.0 - (len(set(retrieved_record_ids)) / len(retrieved_record_ids))
                if retrieved_record_ids
                else 0.0
            )
            language_match = None
            if results:
                detected = classify_language(results[0]["normalized_text"])["language_category"]
                mapped = LANGUAGE_CATEGORY_TO_SANDBOX_LANGUAGE.get(detected, "unknown")
                language_match = mapped == query["language"]
            expected = set(query.get("expected_source_ids") or [])
            metric_availability = "full" if expected else "not_available"
            metrics = {
                "expected_source_hit": None,
                "source_rank": None,
                "recall_at_k": None,
                "precision_at_k": None,
                "reciprocal_rank": None,
            }
            if expected:
                top_k = len(retrieved_record_ids) or 1
                metrics["recall_at_k"] = recall_at_k(retrieved_record_ids, expected, top_k)
                metrics["precision_at_k"] = precision_at_k(
                    retrieved_record_ids, expected, top_k
                )
                metrics["reciprocal_rank"] = mean_reciprocal_rank(retrieved_record_ids, expected)
                metrics["expected_source_hit"] = bool(
                    hit_rate(retrieved_record_ids, expected)
                )
                for rank, record_id in enumerate(retrieved_record_ids, start=1):
                    if record_id in expected:
                        metrics["source_rank"] = rank
                        break

            insufficient_evidence_behavior = None
            if query["query_type"] == "insufficient_evidence":
                insufficient_evidence_behavior = (
                    "correct_no_results" if not results else "unexpected_results"
                )

            self._sandbox.add_retrieval_result(
                run["public_id"],
                {
                    "query_public_id": query["public_id"],
                    "rag_retrieval_run_id": None,
                    "metric_availability": metric_availability,
                    "expected_source_hit": metrics["expected_source_hit"],
                    "source_rank": metrics["source_rank"],
                    "recall_at_k": metrics["recall_at_k"],
                    "precision_at_k": metrics["precision_at_k"],
                    "reciprocal_rank": metrics["reciprocal_rank"],
                    "language_match": language_match,
                    "duplicate_result_rate": duplicate_result_rate,
                    "conflicting_source_retrieved": len(set(retrieved_record_ids)) > 1
                    and query["query_type"] == "conflicting_sources",
                    "insufficient_evidence_behavior": insufficient_evidence_behavior,
                    "latency_milliseconds": retrieval_result.get("runtime_milliseconds"),
                    "result_count": len(results),
                },
            )

        self._sandbox.record_event(
            experiment_public_id,
            {
                "event_type": "retrieval_run_completed",
                "summary": f"retrieval run completed for {len(queries)} queries",
                "metadata": {"retrieval_run_public_id": run["public_id"]},
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="run_retrieval",
            actor_reference=admin_id,
            resource_public_id=experiment_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"query_count": len(queries)},
        )
        return self._sandbox.get_retrieval_run(run["public_id"])


__all__ = ["RagSandboxRetrievalService"]
