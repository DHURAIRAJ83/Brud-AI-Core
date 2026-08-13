"""MB-17: RAG Memory -- pure. Assembles the permanent rollup record a
future phase (MB-18/19/20) can reuse: query, evidence summary, final
answer, confidence, admin decision, hallucination flag, correction
history, and retrieval latency. Every field is already-known data --
no new measurement happens here.
"""

from __future__ import annotations

from typing import Any


def build_rag_memory(
    *, query: str, evidence_counts_by_type: dict[str, int], final_answer: str | None,
    confidence: float | None, hallucination_flag: bool, correction_history: list[dict[str, Any]],
    retrieval_latency_ms: float | None,
) -> dict[str, Any]:
    return {
        "query": query,
        "evidence_summary": {"counts_by_type": evidence_counts_by_type},
        "final_answer": final_answer,
        "confidence": confidence,
        "hallucination_flag": hallucination_flag,
        "correction_history": correction_history,
        "retrieval_latency_ms": retrieval_latency_ms,
    }
