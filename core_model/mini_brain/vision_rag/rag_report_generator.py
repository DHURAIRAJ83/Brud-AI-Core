"""MB-17: RAG Report -- pure assembly only. Merges every stage's
already-computed output into the single document the admin reviews:
Retrieval, Evidence, Hallucination, and Usage sub-sections in one
report, plus a Ready/Needs Review/Not Ready verdict. Never recomputes
anything.
"""

from __future__ import annotations

from typing import Any

READY_THRESHOLD = 75.0
NEEDS_REVIEW_THRESHOLD = 40.0


def generate_rag_report(
    *, vision_rag_session_public_id: str, query: str, quality_report: dict[str, Any],
    evidence_report: dict[str, Any], hallucination_report: dict[str, Any], answer_status: str,
    retrieval_latency_ms: float | None,
) -> dict[str, Any]:
    overall = quality_report["overall_rag_quality"]
    if hallucination_report["hallucination_flag"]:
        status = "Not Ready"
    elif overall >= READY_THRESHOLD:
        status = "Ready"
    elif overall >= NEEDS_REVIEW_THRESHOLD:
        status = "Needs Review"
    else:
        status = "Not Ready"

    problems: list[str] = []
    suggestions: list[str] = []
    if hallucination_report["hallucination_flag"]:
        problems.append(f"hallucination risk {hallucination_report['hallucination_risk']} exceeds threshold")
        suggestions.append("review citations before approving this answer")
    if answer_status == "insufficient_evidence":
        problems.append("insufficient evidence to answer this query")
    if evidence_report["evidence_count"] == 0:
        problems.append("no evidence was retrieved for this query")

    return {
        "vision_rag_session_public_id": vision_rag_session_public_id, "query": query,
        "status": status, "overall_rag_quality": overall, "components": quality_report["components"],
        "retrieval_report": evidence_report["counts_by_type"],
        "evidence_report": {"evidence_count": evidence_report["evidence_count"]},
        "hallucination_report": hallucination_report,
        "usage_report": {"retrieval_latency_ms": retrieval_latency_ms},
        "problems": problems, "suggestions": suggestions,
        "recommendation": "approve" if status == "Ready" else "reject" if hallucination_report["hallucination_flag"] else "request_changes",
        "risk": "Low" if status == "Ready" else "Medium" if status == "Needs Review" else "High",
        "ready_for_admin_review": True,
    }
