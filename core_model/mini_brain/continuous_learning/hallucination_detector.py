"""MB-08: Hallucination Detector -- pure. Classifies already-fetched
Public Chat routing events by their real `evidence_status` field
(computed by the existing RAG/routing pipeline, never re-derived
here) into the task spec's three named signals:
  - unsupported claims: evidence_status == 'model_only' (an answer was
    generated with no retrieved evidence backing it) or 'none'
  - missing citations: evidence_status == 'insufficient'
  - inconsistent answers: evidence_status == 'conflicting' (retrieved
    evidence itself disagreed)
"model_only'/'none' is the closest real signal to "unsupported claim"
this system produces; there is no separate claim-level fact-checker to
reuse or duplicate.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

UNSUPPORTED_CLAIM_STATUSES = frozenset({"model_only", "none"})
MISSING_CITATION_STATUSES = frozenset({"insufficient"})
INCONSISTENT_STATUSES = frozenset({"conflicting"})


def detect_hallucinations(*, routing_events: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(routing_events)
    by_evidence_status = Counter(e["evidence_status"] for e in routing_events)

    unsupported = sum(by_evidence_status.get(s, 0) for s in UNSUPPORTED_CLAIM_STATUSES)
    missing_citations = sum(by_evidence_status.get(s, 0) for s in MISSING_CITATION_STATUSES)
    inconsistent = sum(by_evidence_status.get(s, 0) for s in INCONSISTENT_STATUSES)
    grounded = by_evidence_status.get("grounded", 0) + by_evidence_status.get("partially_grounded", 0)

    hallucination_signal_count = unsupported + missing_citations + inconsistent
    return {
        "total_conversations_observed": total,
        "by_evidence_status": dict(by_evidence_status),
        "unsupported_claim_count": unsupported,
        "missing_citation_count": missing_citations,
        "inconsistent_answer_count": inconsistent,
        "grounded_count": grounded,
        "hallucination_signal_count": hallucination_signal_count,
        "hallucination_rate": round(hallucination_signal_count / total, 4) if total else None,
    }
