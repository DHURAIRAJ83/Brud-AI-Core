"""MB-17: shared relevance scoring -- pure. Every retrieval layer
(text/OCR/image/object) scores its own candidates against the query
through this one function, which composes the real, already-tested
`core_model.rag` primitives directly: `embed_local_custom()` for a
real deterministic embedding (the genuine local embedding path this
codebase already has, not a fabricated similarity), `score_vectors()`
for cosine similarity, and `tokenize_for_keyword_index()` for a real
keyword-overlap signal blended in alongside it. This is the one place
MB-17 composes retrieval math, so every layer scores candidates
identically -- never a second, divergent implementation.
"""

from __future__ import annotations

from typing import Any

from core_model.rag.embedding import embed_local_custom
from core_model.rag.keyword_index import tokenize_for_keyword_index
from core_model.rag.vector_index import normalize_scores, score_vectors

EMBEDDING_DIMENSIONS = 128
VECTOR_WEIGHT = 0.6
KEYWORD_WEIGHT = 0.4


def score_candidates(*, normalized_query: str, candidate_texts: list[str]) -> list[float]:
    if not candidate_texts:
        return []

    query_vector = embed_local_custom(normalized_query, dimensions=EMBEDDING_DIMENSIONS)
    candidate_vectors = [
        embed_local_custom(text, dimensions=EMBEDDING_DIMENSIONS) for text in candidate_texts
    ]
    vector_scores = normalize_scores(score_vectors(query_vector, candidate_vectors, distance_metric="cosine"))

    query_tokens = set(tokenize_for_keyword_index(normalized_query))
    keyword_scores: list[float] = []
    for text in candidate_texts:
        candidate_tokens = set(tokenize_for_keyword_index(text))
        if not query_tokens or not candidate_tokens:
            keyword_scores.append(0.0)
            continue
        overlap = len(query_tokens & candidate_tokens)
        keyword_scores.append(overlap / len(query_tokens))
    keyword_scores = normalize_scores(keyword_scores) if any(keyword_scores) else keyword_scores

    return [
        round(VECTOR_WEIGHT * v + KEYWORD_WEIGHT * k, 4)
        for v, k in zip(vector_scores, keyword_scores, strict=True)
    ]


def top_candidates(
    *, items: list[dict[str, Any]], scores: list[float], limit: int, minimum_score: float = 0.05,
) -> list[dict[str, Any]]:
    paired = sorted(zip(items, scores, strict=True), key=lambda pair: -pair[1])
    return [
        {**item, "relevance_score": score} for item, score in paired
        if score >= minimum_score
    ][:limit]
