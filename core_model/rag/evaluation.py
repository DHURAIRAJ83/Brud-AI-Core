"""Retrieval and generation evaluation metrics.

Computed only from fixtures with known relevant chunk/source IDs —
never fabricated relevance labels. Retrieval and generation failure are
always reported separately from each other.
"""

from __future__ import annotations

import math
from typing import Any

RETRIEVAL_METRIC_KEYS = (
    "recall_at_k",
    "precision_at_k",
    "mrr",
    "ndcg_at_k",
    "hit_rate",
    "language_match",
    "source_diversity_rate",
    "duplicate_result_rate",
    "blocked_chunk_exclusion_rate",
    "no_answer_correct",
    "latency_ms",
)

GENERATION_METRIC_KEYS = (
    "citation_validity_rate",
    "citation_coverage_rate",
    "unsupported_claim_rate",
    "unknown_citation_rate",
    "no_answer_appropriate",
    "answer_language_compliant",
    "grounding_score",
    "role_leakage",
    "injection_resistance",
)


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    return len(top_k & relevant_ids) / len(relevant_ids)


def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for candidate in top_k if candidate in relevant_ids)
    return hits / len(top_k)


def mean_reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    for index, candidate in enumerate(retrieved_ids, start=1):
        if candidate in relevant_ids:
            return 1.0 / index
    return 0.0


def dcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    score = 0.0
    for index, candidate in enumerate(retrieved_ids[:k], start=1):
        relevance = 1.0 if candidate in relevant_ids else 0.0
        score += relevance / math.log2(index + 1)
    return score


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    actual = dcg_at_k(retrieved_ids, relevant_ids, k)
    ideal_count = min(len(relevant_ids), k)
    ideal = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_count + 1))
    return actual / ideal if ideal > 0 else 0.0


def hit_rate(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    return 1.0 if set(retrieved_ids) & relevant_ids else 0.0


def finite_or_none(value: float | None) -> float | None:
    if value is None:
        return None
    if value != value or value in (float("inf"), float("-inf")):  # noqa: PLR0124
        return None
    return value


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


def aggregate_generation_metrics(per_fixture_results: list[dict[str, Any]]) -> dict[str, Any]:
    return _aggregate(per_fixture_results, GENERATION_METRIC_KEYS)
