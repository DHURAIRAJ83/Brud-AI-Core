"""Chat orchestration response status policy.

Nine statuses: completed, completed_with_warning, insufficient_evidence,
memory_conflict, consent_required, retrieval_failed, generation_failed,
blocked_context, session_closed. A response must never claim a memory
is verified when it was only inferred, and missing consent must never
be silently bypassed.
"""

from __future__ import annotations

from typing import Any


def decide_response_status(
    *,
    session_closed: bool,
    context_blocked: bool,
    retrieval_failed: bool,
    generation_failed: bool,
    consent_required: bool,
    unresolved_memory_conflict: bool,
    no_evidence_available: bool,
    citation_validity_rate: float | None,
    minimum_citation_validity_rate: float = 0.5,
) -> dict[str, Any]:
    if session_closed:
        return {"status": "session_closed", "reason": "session_closed"}
    if context_blocked:
        return {"status": "blocked_context", "reason": "injection_blocked_context"}
    if retrieval_failed:
        return {"status": "retrieval_failed", "reason": "retrieval_failed"}
    if consent_required:
        return {"status": "consent_required", "reason": "memory_consent_required"}
    if unresolved_memory_conflict:
        return {"status": "memory_conflict", "reason": "unresolved_memory_conflict"}
    if no_evidence_available:
        return {"status": "insufficient_evidence", "reason": "no_evidence_available"}
    if generation_failed:
        return {"status": "generation_failed", "reason": "generation_failed"}
    if (
        citation_validity_rate is not None
        and citation_validity_rate < minimum_citation_validity_rate
    ):
        return {"status": "insufficient_evidence", "reason": "citation_validation_failed"}
    if citation_validity_rate is not None and citation_validity_rate < 1.0:
        return {"status": "completed_with_warning", "reason": "some_citations_invalid"}
    return {"status": "completed", "reason": None}


def memory_disclosure(
    *, memory_used: bool, memory_item_public_ids: list[str], memory_purposes: list[str]
) -> dict[str, Any]:
    return {
        "memory_used": memory_used,
        "memory_item_public_ids": memory_item_public_ids if memory_used else [],
        "memory_purpose": memory_purposes if memory_used else [],
    }
