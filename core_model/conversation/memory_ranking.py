"""Deterministic memory ranking.

Combines keyword, vector, recency, user-confirmed-boost, purpose-match,
session-relevance, conflict-penalty, and staleness-penalty signals into
one bounded combined score. Never claims probability calibration --
scores are for ranking only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MemoryRankingWeights:
    keyword_weight: float = 0.4
    vector_weight: float = 0.6
    recency_weight: float = 0.1
    user_confirmed_boost: float = 0.2
    session_relevance_boost: float = 0.05
    conflict_penalty: float = 0.3
    staleness_penalty: float = 0.15


def compute_combined_score(
    *,
    keyword_score: float | None,
    vector_score: float | None,
    recency_score: float | None,
    is_user_confirmed: bool,
    is_session_relevant: bool,
    has_conflict: bool,
    is_stale: bool,
    weights: MemoryRankingWeights,
) -> float:
    score = 0.0
    if keyword_score is not None:
        score += weights.keyword_weight * keyword_score
    if vector_score is not None:
        score += weights.vector_weight * vector_score
    if recency_score is not None:
        score += weights.recency_weight * recency_score
    if is_user_confirmed:
        score += weights.user_confirmed_boost
    if is_session_relevant:
        score += weights.session_relevance_boost
    if has_conflict:
        score -= weights.conflict_penalty
    if is_stale:
        score -= weights.staleness_penalty
    if score != score or score in (float("inf"), float("-inf")):  # noqa: PLR0124
        raise ValueError("combined score must be finite")
    return max(0.0, score)


def rank_with_tie_break(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(
        scored, key=lambda entry: (-entry["combined_score"], entry["memory_item_public_id"])
    )
    for index, entry in enumerate(ordered, start=1):
        entry["rank"] = index
    return ordered
