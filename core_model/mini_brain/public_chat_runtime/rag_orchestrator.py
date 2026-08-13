"""MB-23: RAG Orchestrator -- pure. Derives `used_rag` and evidence-
sufficiency flags from fields `PublicChatResponse` already carries
(`source_types`, `evidence_status`, `citations`, `insufficient_evidence`)
-- MB-23 never retrieves anything itself; `RagRetrievalService`,
reached only through `PublicChatRoutingService.handle_message()`, is
the sole real retriever in the codebase.
"""

from __future__ import annotations

from typing import Any

_INSUFFICIENT_EVIDENCE_STATUSES = frozenset({"insufficient", "conflicting", "none"})


def derive_rag_usage(
    *, source_types: list[str], evidence_status: str, citation_count: int, insufficient_evidence: bool,
) -> dict[str, Any]:
    used_rag = "rag" in source_types or citation_count > 0
    evidence_sufficient = not insufficient_evidence and evidence_status not in _INSUFFICIENT_EVIDENCE_STATUSES
    return {
        "used_rag": used_rag, "evidence_status": evidence_status, "citation_count": citation_count,
        "evidence_sufficient": evidence_sufficient,
        "disclosure": "derived from PublicChatResponse's own already-computed evidence fields -- no retrieval is performed by this module",
    }
