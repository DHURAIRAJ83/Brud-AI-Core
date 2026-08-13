"""MB-08: Knowledge Gap Detector -- pure. Aggregates already-fetched
Knowledge Gap Registry cases (`event_type == 'knowledge_gap'`) into
the task spec's four groupings, from real fields only:
  - missing domains: grouped by the case's own `domain` field
  - missing concepts: grouped by the case's own `intent` field
  - missing documentation: cases whose reason codes include
    rag_content_missing/rag_retrieval_insufficient (the registry's
    real "no retrievable evidence" signal)
  - missing workflows/concepts: cases whose reason codes include
    domain_understanding_missing/model_knowledge_missing (the
    registry's real "the model itself doesn't know this" signal)

The documentation/workflow split does not exist as a distinct
taxonomy anywhere in the reused system -- it is this module's own
disclosed mapping over the registry's real, existing reason codes,
not a fabricated new signal.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

DOCUMENTATION_REASON_CODES = frozenset({"rag_content_missing", "rag_retrieval_insufficient"})
WORKFLOW_REASON_CODES = frozenset({"domain_understanding_missing", "model_knowledge_missing"})


def detect_knowledge_gaps(*, knowledge_gap_cases: list[dict[str, Any]]) -> dict[str, Any]:
    cases = [c for c in knowledge_gap_cases if c["event_type"] == "knowledge_gap"]

    by_domain = Counter(c["domain"] or "unclassified" for c in cases)
    by_intent = Counter(c["intent"] or "unclassified" for c in cases)

    documentation_gaps = [
        c for c in cases if any(code in DOCUMENTATION_REASON_CODES for code in c["reason_codes"])
    ]
    workflow_gaps = [
        c for c in cases if any(code in WORKFLOW_REASON_CODES for code in c["reason_codes"])
    ]

    return {
        "total_knowledge_gap_cases": len(cases),
        "missing_domains": [
            {"domain": domain, "case_count": count} for domain, count in by_domain.most_common()
        ],
        "missing_concepts": [
            {"intent": intent, "case_count": count} for intent, count in by_intent.most_common()
        ],
        "missing_documentation_count": len(documentation_gaps),
        "missing_documentation_domains": sorted({c["domain"] for c in documentation_gaps if c["domain"]}),
        "missing_workflow_count": len(workflow_gaps),
        "missing_workflow_domains": sorted({c["domain"] for c in workflow_gaps if c["domain"]}),
    }
