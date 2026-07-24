"""Deterministic hybrid retrieval scoring.

Combines normalized vector and keyword scores plus bounded metadata
boosts using a fixed, documented formula. Never claims probability
calibration — scores are a bounded ranking signal only. Tie-breaking is
always deterministic (never hidden randomness).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HybridScoreInputs:
    chunk_public_id: str
    source_public_id: str
    content_checksum_sha256: str
    vector_score: float | None
    keyword_score: float | None
    is_heading_match: bool = False
    is_exact_match: bool = False
    language_match: bool = False


@dataclass(frozen=True)
class HybridWeights:
    vector_weight: float = 0.6
    keyword_weight: float = 0.4
    heading_boost: float = 0.05
    exact_match_boost: float = 0.1
    language_match_boost: float = 0.05


def compute_combined_score(
    inputs: HybridScoreInputs, weights: HybridWeights
) -> dict[str, Any]:
    vector_component = (inputs.vector_score or 0.0) * weights.vector_weight
    keyword_component = (inputs.keyword_score or 0.0) * weights.keyword_weight
    boost = 0.0
    if inputs.is_heading_match:
        boost += weights.heading_boost
    if inputs.is_exact_match:
        boost += weights.exact_match_boost
    if inputs.language_match:
        boost += weights.language_match_boost
    combined = vector_component + keyword_component + boost
    if combined != combined or combined in (float("inf"), float("-inf")):  # noqa: PLR0124
        raise ValueError("combined score is not finite")

    return {
        "chunk_public_id": inputs.chunk_public_id,
        "source_public_id": inputs.source_public_id,
        "content_checksum_sha256": inputs.content_checksum_sha256,
        "vector_score": inputs.vector_score,
        "keyword_score": inputs.keyword_score,
        "combined_score": combined,
        "language_match": inputs.language_match,
    }


def collapse_exact_duplicates(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keeps only the highest-scoring entry per exact content checksum,
    with a deterministic tie-break on ``chunk_public_id``."""

    best_by_checksum: dict[str, dict[str, Any]] = {}
    for entry in scored:
        checksum = entry.get("content_checksum_sha256") or entry["chunk_public_id"]
        existing = best_by_checksum.get(checksum)
        if existing is None:
            best_by_checksum[checksum] = entry
            continue
        if entry["combined_score"] > existing["combined_score"] or (
            entry["combined_score"] == existing["combined_score"]
            and entry["chunk_public_id"] < existing["chunk_public_id"]
        ):
            best_by_checksum[checksum] = entry
    return list(best_by_checksum.values())


def rank_with_tie_break(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Highest combined score first; ties broken deterministically by
    ``chunk_public_id`` ascending — never hidden random ranking."""

    ranked = sorted(scored, key=lambda entry: (-entry["combined_score"], entry["chunk_public_id"]))
    for rank, entry in enumerate(ranked, start=1):
        entry["rank"] = rank
    return ranked


def enforce_source_diversity(
    ranked: list[dict[str, Any]], *, max_per_source: int, top_k: int
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    selected: list[dict[str, Any]] = []
    overflow: list[dict[str, Any]] = []
    for entry in ranked:
        source = entry.get("source_public_id", "")
        if counts.get(source, 0) < max_per_source:
            selected.append(entry)
            counts[source] = counts.get(source, 0) + 1
        else:
            overflow.append(entry)
        if len(selected) >= top_k:
            break
    if len(selected) < top_k:
        selected.extend(overflow[: top_k - len(selected)])
    return selected[:top_k]
