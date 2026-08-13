"""MB-19: Grounding Benchmark -- pure. Reuses MB-17's own already-
computed `hallucination_report.citation_validity_rate` per session
directly, plus the production RAG grounding module's own
`unsupported_sentence_ratio()` applied to MB-17's own already-generated
answer text -- never a second citation-validity or sentence-splitting
implementation.
"""

from __future__ import annotations

from typing import Any

from core_model.rag.grounding_checks import unsupported_sentence_ratio


def run_grounding_benchmark(*, rag_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """`rag_sessions`: one entry per evaluated MB-17 session, each
    ``{"answer": str | None, "citation_validity_rate": float | None,
    "cited_evidence_count": int, "total_evidence_count": int}``."""
    if not rag_sessions:
        return {
            "session_count": 0, "citation_validity_rate": None, "evidence_coverage_rate": None,
            "unsupported_sentence_ratio": None,
            "disclosure": "no MB-17 RAG session was supplied -- grounding benchmark is honestly unavailable",
        }

    unsupported_ratios = [
        unsupported_sentence_ratio(session["answer"]) for session in rag_sessions if session.get("answer")
    ]
    citation_rates = [
        session["citation_validity_rate"] for session in rag_sessions
        if session.get("citation_validity_rate") is not None
    ]
    coverage_rates = [
        session["cited_evidence_count"] / session["total_evidence_count"] for session in rag_sessions
        if session.get("total_evidence_count")
    ]

    return {
        "session_count": len(rag_sessions),
        "citation_validity_rate": round(sum(citation_rates) / len(citation_rates), 3) if citation_rates else None,
        "evidence_coverage_rate": round(sum(coverage_rates) / len(coverage_rates), 3) if coverage_rates else None,
        "unsupported_sentence_ratio": (
            round(sum(unsupported_ratios) / len(unsupported_ratios), 3) if unsupported_ratios else None
        ),
        "disclosure": (
            "citation_validity_rate is read directly from MB-17's own already-computed hallucination "
            "check, never recomputed here; unsupported_sentence_ratio is measured on MB-17's own "
            "already-generated answer text using the production RAG system's own sentence-citation "
            "scanner"
        ),
    }
