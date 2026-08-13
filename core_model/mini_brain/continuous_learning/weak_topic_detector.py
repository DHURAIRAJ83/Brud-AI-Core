"""MB-08: Weak Topic Detector -- pure. Ranks domains by a real,
evidence-grounded weakness index built from already-fetched Knowledge
Gap Registry cases.

Honest scope: no system in this codebase tracks per-domain
conversation volume or a true per-domain accuracy percentage --
`knowledge_gap_cases` only records FAILURES/gaps, never successes, and
routing events carry no domain tag at all. A literal "Python 92%
correct" figure like the task spec's example is therefore not
measurable from real data today. Rather than fabricate one, this
module computes a disclosed `weakness_index` (0-100, higher = weaker)
from real, already-computed signals only: how many registry cases a
domain has, and their real, already-computed `priority_score` average
-- both genuinely produced by the existing Knowledge Gap Registry, not
invented here. The weighting formula itself is a fixed, disclosed
heuristic, not empirically validated against real outcomes.
"""

from __future__ import annotations

from typing import Any

WEAK_THRESHOLD = 30.0
CASE_COUNT_WEIGHT = 10.0


def detect_weak_topics(*, knowledge_gap_cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_domain: dict[str, list[dict[str, Any]]] = {}
    for case in knowledge_gap_cases:
        domain = case["domain"] or "unclassified"
        by_domain.setdefault(domain, []).append(case)

    topics = []
    for domain, cases in by_domain.items():
        case_count = len(cases)
        avg_priority_score = sum(c["priority_score"] for c in cases) / case_count
        weakness_index = round(min(100.0, case_count * CASE_COUNT_WEIGHT + avg_priority_score), 1)
        topics.append({
            "domain": domain,
            "case_count": case_count,
            "average_priority_score": round(avg_priority_score, 2),
            "weakness_index": weakness_index,
            "classification": "Weak" if weakness_index >= WEAK_THRESHOLD else "Strong",
        })

    topics.sort(key=lambda t: t["weakness_index"], reverse=True)
    return {
        "topics": topics,
        "weak_topics": [t["domain"] for t in topics if t["classification"] == "Weak"],
        "strong_topics": [t["domain"] for t in topics if t["classification"] == "Strong"],
    }
