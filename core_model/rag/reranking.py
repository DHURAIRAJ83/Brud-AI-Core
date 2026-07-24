"""Deterministic, CPU-light reranking signals.

Phase 16 does not use the answer-generation model as a reranker; every
signal here is a bounded, explainable heuristic.
"""

from __future__ import annotations

from dataclasses import dataclass

_INJECTION_PENALTIES = {"clean": 0.0, "warning": 0.05, "quarantined": 0.5, "blocked": 1.0}


@dataclass(frozen=True)
class RerankInputs:
    query_tokens: frozenset[str]
    chunk_tokens: frozenset[str]
    heading_match: bool
    language_match: bool
    source_priority: float
    chunk_token_count: int
    target_chunk_tokens: int
    is_duplicate_flagged: bool
    injection_status: str


def query_token_coverage(query_tokens: frozenset[str], chunk_tokens: frozenset[str]) -> float:
    if not query_tokens:
        return 0.0
    return len(query_tokens & chunk_tokens) / len(query_tokens)


def length_penalty(chunk_token_count: int, target_chunk_tokens: int) -> float:
    if target_chunk_tokens <= 0:
        return 0.0
    ratio = chunk_token_count / target_chunk_tokens
    if ratio <= 1.5:
        return 0.0
    return min(0.3, (ratio - 1.5) * 0.1)


def injection_penalty(injection_status: str) -> float:
    return _INJECTION_PENALTIES.get(injection_status, 0.0)


def compute_rerank_score(inputs: RerankInputs) -> float:
    score = query_token_coverage(inputs.query_tokens, inputs.chunk_tokens)
    if inputs.heading_match:
        score += 0.1
    if inputs.language_match:
        score += 0.05
    score += 0.1 * max(0.0, min(1.0, inputs.source_priority))
    score -= length_penalty(inputs.chunk_token_count, inputs.target_chunk_tokens)
    if inputs.is_duplicate_flagged:
        score -= 0.2
    score -= injection_penalty(inputs.injection_status)
    return max(0.0, score)
