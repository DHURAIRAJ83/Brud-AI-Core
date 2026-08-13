"""MB-09: Knowledge Gap Evolution -- pure. Compares already-fetched
MB-08 Continuous Learning Reports (oldest to newest, real data MB-08
already produced) to detect recurring weaknesses, ranked by a
disclosed long-term-importance score: how many cycles a domain kept
showing up as Weak, weighted by its most recent weakness index.

Honest scope: MB-08's reports have no distinct "user request" concept
-- recurring knowledge-gap domains (`knowledge_coverage.missing_domains`)
are the closest real proxy and are reported as such, not invented as a
separate signal.
"""

from __future__ import annotations

from typing import Any

RECURRENCE_THRESHOLD = 2
HIGH_FAILURE_RATE = 0.20
HIGH_HALLUCINATION_RATE = 0.20


def evolve_knowledge_gaps(*, reports: list[dict[str, Any]]) -> dict[str, Any]:
    domain_recurrence: dict[str, int] = {}
    domain_latest_weakness: dict[str, float] = {}
    for report in reports:
        for area in report.get("weak_areas", []):
            domain = area["domain"]
            domain_recurrence[domain] = domain_recurrence.get(domain, 0) + 1
            domain_latest_weakness[domain] = area["weakness_index"]

    recurring_weak_domains = [
        {
            "domain": domain, "recurrence_count": count,
            "latest_weakness_index": domain_latest_weakness[domain],
            "long_term_importance": round(count * domain_latest_weakness[domain], 2),
        }
        for domain, count in domain_recurrence.items() if count >= RECURRENCE_THRESHOLD
    ]
    recurring_weak_domains.sort(key=lambda d: d["long_term_importance"], reverse=True)

    gap_domain_recurrence: dict[str, int] = {}
    for report in reports:
        for entry in report.get("knowledge_coverage", {}).get("missing_domains", []):
            domain = entry["domain"]
            gap_domain_recurrence[domain] = gap_domain_recurrence.get(domain, 0) + 1
    unresolved_knowledge_gaps = sorted(
        [
            {"domain": d, "recurrence_count": c}
            for d, c in gap_domain_recurrence.items() if c >= RECURRENCE_THRESHOLD
        ],
        key=lambda d: d["recurrence_count"], reverse=True,
    )

    failure_rates = [r["failure_rate"] for r in reports if r.get("failure_rate") is not None]
    hallucination_rates = [r["hallucination_rate"] for r in reports if r.get("hallucination_rate") is not None]
    recurring_high_failure_cycles = sum(1 for rate in failure_rates if rate >= HIGH_FAILURE_RATE)
    recurring_high_hallucination_cycles = sum(
        1 for rate in hallucination_rates if rate >= HIGH_HALLUCINATION_RATE
    )

    return {
        "cycles_compared": len(reports),
        "recurring_weak_domains": recurring_weak_domains,
        "unresolved_knowledge_gaps": unresolved_knowledge_gaps,
        "recurring_high_failure_cycle_count": recurring_high_failure_cycles,
        "recurring_high_hallucination_cycle_count": recurring_high_hallucination_cycles,
        "recurring_failures_detected": recurring_high_failure_cycles >= RECURRENCE_THRESHOLD,
        "recurring_hallucinations_detected": recurring_high_hallucination_cycles >= RECURRENCE_THRESHOLD,
    }
