"""MB-18: Grounding Quality Analyzer -- pure. Reuses MB-17's own
already-computed RAG Memory (confidence, hallucination flag) across
every accepted grounded query -- never re-runs retrieval or re-checks
citations itself.
"""

from __future__ import annotations

from typing import Any


def analyze_grounding_quality(*, rag_memory_entries: list[dict[str, Any]]) -> dict[str, Any]:
    if not rag_memory_entries:
        return {
            "query_count": 0, "average_confidence": None, "hallucination_flag_count": 0,
            "hallucination_rate": None,
            "disclosure": "no MB-17 grounded RAG memory was linked -- grounding quality is honestly unavailable, not assumed perfect",
        }

    confidences = [m["confidence"] for m in rag_memory_entries if m.get("confidence") is not None]
    flagged = sum(1 for m in rag_memory_entries if m.get("hallucination_flag"))

    return {
        "query_count": len(rag_memory_entries),
        "average_confidence": round(sum(confidences) / len(confidences), 3) if confidences else None,
        "hallucination_flag_count": flagged,
        "hallucination_rate": round(flagged / len(rag_memory_entries), 3),
    }
