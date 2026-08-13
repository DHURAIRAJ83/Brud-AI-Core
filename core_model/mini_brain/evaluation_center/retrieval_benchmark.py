"""MB-19: Retrieval Benchmark -- pure. Aggregates MB-17's own already-
computed evidence counts, relevance scores, and answer status per
session -- never re-runs retrieval itself.
"""

from __future__ import annotations

from typing import Any


def run_retrieval_benchmark(*, rag_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """`rag_sessions`: one entry per evaluated MB-17 session, each
    ``{"evidence_count": int, "average_relevance_score": float | None,
    "answer_status": str | None}``."""
    if not rag_sessions:
        return {
            "session_count": 0, "topk_evidence_availability": None, "average_relevance_score": None,
            "insufficient_evidence_rate": None,
            "disclosure": "no MB-17 RAG session was supplied -- retrieval benchmark is honestly unavailable",
        }

    total = len(rag_sessions)
    with_evidence = sum(1 for session in rag_sessions if session.get("evidence_count", 0) > 0)
    insufficient = sum(1 for session in rag_sessions if session.get("answer_status") == "insufficient_evidence")
    relevance_scores = [
        session["average_relevance_score"] for session in rag_sessions
        if session.get("average_relevance_score") is not None
    ]

    return {
        "session_count": total,
        "topk_evidence_availability": round(with_evidence / total, 3),
        "average_relevance_score": (
            round(sum(relevance_scores) / len(relevance_scores), 3) if relevance_scores else None
        ),
        "insufficient_evidence_rate": round(insufficient / total, 3),
        "disclosure": (
            "retrieval quality is measured entirely against MB-17's own already-stored evidence -- "
            "this never re-runs retrieval and never judges whether the retrieved evidence was the "
            "objectively best possible result, only whether evidence was present and used"
        ),
    }
