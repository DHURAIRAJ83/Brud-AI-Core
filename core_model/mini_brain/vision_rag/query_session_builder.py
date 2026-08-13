"""MB-17: Query Session builder -- pure. Stage 1 classifies the query's
language and normalizes it, reusing `core_model.rag.language_routing.
classify_language()` and `core_model.rag.query_normalization.
normalize_query()` directly -- the same deterministic, non-ML language
routing the production RAG system already uses. Never a new language-
detection implementation.
"""

from __future__ import annotations

from typing import Any

from core_model.rag.language_routing import classify_language
from core_model.rag.query_normalization import normalize_query


def build_query_session(*, query: str, multimodal_dataset_status: str) -> dict[str, Any]:
    dataset_certified = multimodal_dataset_status == "admin_approved"
    language_info = classify_language(query)
    normalization = normalize_query(query, language_category=language_info["language_category"])

    return {
        "query": query, "normalized_query": normalization["normalized_query"],
        "language_category": language_info["language_category"],
        "dataset_certified": dataset_certified,
        "ready": dataset_certified and bool(query.strip()),
        "disclosure": (
            "requires an already-certified MB-16 dataset -- every retrieval result must remain "
            "evidence-linked, which only holds once the underlying dataset has been through admin "
            "certification"
        ),
    }
