"""Memory retrieval and conversation orchestration evaluation metrics.

Retrieval ranking metrics (recall/precision/MRR/nDCG/hit-rate) are the
same generic, well-defined math already implemented and unit-tested in
Phase 16 -- re-exported here unchanged rather than re-implemented, per
the project's reuse-over-duplication discipline. Metrics are computed
only from fixtures with known relevant/excluded IDs, never fabricated
relevance labels.
"""

from __future__ import annotations

from typing import Any

from core_model.rag.evaluation import (
    dcg_at_k,
    finite_or_none,
    hit_rate,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)

__all__ = [
    "recall_at_k",
    "precision_at_k",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "dcg_at_k",
    "hit_rate",
    "aggregate_retrieval_metrics",
    "aggregate_orchestration_metrics",
    "owner_filter_accuracy",
    "exclusion_rate",
]

RETRIEVAL_METRIC_KEYS = (
    "recall_at_k",
    "precision_at_k",
    "mrr",
    "ndcg_at_k",
    "hit_rate",
    "owner_filter_accuracy",
    "deleted_exclusion_rate",
    "expired_exclusion_rate",
    "revoked_exclusion_rate",
    "conflict_detection_accuracy",
    "language_preference_retrieval_accuracy",
    "latency_ms",
)

ORCHESTRATION_METRIC_KEYS = (
    "latest_turn_preservation_rate",
    "context_budget_compliance_rate",
    "summary_faithfulness_rate",
    "memory_use_correctness_rate",
    "rag_citation_validity_rate",
    "language_continuity_accuracy",
    "no_memory_privacy_compliance_rate",
    "cross_session_isolation_rate",
    "injection_resistance_rate",
)


def owner_filter_accuracy(retrieved_ids: list[str], expected_owner_ids: set[str]) -> float:
    if not retrieved_ids:
        return 1.0
    correct = sum(1 for item_id in retrieved_ids if item_id in expected_owner_ids)
    return correct / len(retrieved_ids)


def exclusion_rate(excluded_ids_expected: set[str], actually_retrieved_ids: set[str]) -> float:
    """Fraction of ids that were correctly excluded (never appear among
    actually_retrieved_ids). 1.0 means perfect exclusion."""

    if not excluded_ids_expected:
        return 1.0
    wrongly_included = excluded_ids_expected & actually_retrieved_ids
    return 1.0 - (len(wrongly_included) / len(excluded_ids_expected))


def _aggregate(per_fixture_results: list[dict[str, Any]], keys: tuple[str, ...]) -> dict[str, Any]:
    aggregated: dict[str, Any] = {}
    for key in keys:
        values = [
            finite_or_none(result[key])
            for result in per_fixture_results
            if key in result and result[key] is not None
        ]
        values = [value for value in values if value is not None]
        aggregated[key] = (sum(values) / len(values)) if values else None
    aggregated["sample_size"] = len(per_fixture_results)
    return aggregated


def aggregate_retrieval_metrics(per_fixture_results: list[dict[str, Any]]) -> dict[str, Any]:
    return _aggregate(per_fixture_results, RETRIEVAL_METRIC_KEYS)


def aggregate_orchestration_metrics(per_fixture_results: list[dict[str, Any]]) -> dict[str, Any]:
    return _aggregate(per_fixture_results, ORCHESTRATION_METRIC_KEYS)
