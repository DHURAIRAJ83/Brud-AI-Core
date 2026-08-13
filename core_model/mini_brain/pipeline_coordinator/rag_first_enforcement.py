"""MB-12: RAG First Enforcement -- pure. Gates progression to Training
by checking an already-produced RAG Sandbox report (from
`RagSandboxReportService.finalize()`, read from whichever upstream
phase -- MB-11 or MB-06 -- already ran it) against production
readiness, citation validity, the hallucination-rate threshold row,
and admin approval. MB-12 never runs RAG Sandbox itself -- see the
completion report's Finding 1. On failure, the recommendation is
always to return to Dataset Evolution, exactly as the task spec
requires.
"""

from __future__ import annotations

from typing import Any

MIN_CITATION_VALIDITY_RATE = 0.7
_BLOCKING_READINESS = {"blocked", "not_ready"}


def check_rag_gate(*, rag_report: dict[str, Any] | None, admin_decision: str | None) -> dict[str, Any]:
    if not rag_report:
        return {
            "passed": False, "reasons": ["no RAG report available yet -- RAG Sandbox has not been run"],
            "recommendation": "return_to_dataset_evolution",
        }

    readiness = rag_report.get("production_rag_readiness")
    citation_validity_rate = (rag_report.get("citation_metrics") or {}).get("citation_validity_rate")
    hallucination_row = next(
        (r for r in rag_report.get("threshold_evaluation", []) if r.get("dimension") == "maximum_hallucination_rate"),
        None,
    )
    hallucination_passed = hallucination_row["passed"] if hallucination_row else None

    reasons: list[str] = []
    if readiness in _BLOCKING_READINESS:
        reasons.append(f"production_rag_readiness is '{readiness}'")
    if citation_validity_rate is not None and citation_validity_rate < MIN_CITATION_VALIDITY_RATE:
        reasons.append(f"citation validity rate {citation_validity_rate} is below {MIN_CITATION_VALIDITY_RATE}")
    if hallucination_passed is False:
        reasons.append("hallucination-rate threshold failed")
    if admin_decision != "approve":
        reasons.append("RAG report has not been admin-approved yet")

    passed = not reasons
    return {
        "passed": passed,
        "production_rag_readiness": readiness,
        "citation_validity_rate": citation_validity_rate,
        "hallucination_check_passed": hallucination_passed,
        "admin_approved": admin_decision == "approve",
        "reasons": reasons,
        "recommendation": "proceed_to_training_candidate" if passed else "return_to_dataset_evolution",
    }
