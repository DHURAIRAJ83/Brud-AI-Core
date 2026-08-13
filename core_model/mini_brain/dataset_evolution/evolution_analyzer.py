"""MB-11: Dataset Evolution Analyzer -- pure. Combines already-computed
signals from the current dataset (MB-05/MB-05.1) and recent closed
cycles of MB-08, MB-09, and MB-10 into one complete evolution analysis.
Never recomputes any of those signals itself -- every input here is
another phase's own real output, read-only, at the service layer.
"""

from __future__ import annotations

from typing import Any

MAX_CYCLES_COMPARED = 10


def analyze_evolution(
    *,
    dataset_training: dict[str, Any],
    dataset_analysis: dict[str, Any],
    advanced_report: dict[str, Any],
    mb08_reports: list[dict[str, Any]],
    mb09_sessions: list[dict[str, Any]],
    mb10_sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    recent_mb08 = mb08_reports[:MAX_CYCLES_COMPARED]
    recent_mb09 = mb09_sessions[:MAX_CYCLES_COMPARED]
    recent_mb10 = mb10_sessions[:MAX_CYCLES_COMPARED]

    weak_domains: list[str] = []
    missing_domains: list[str] = []
    failure_rates: list[float] = []
    hallucination_rates: list[float] = []
    for report in recent_mb08:
        weak_domains.extend(report.get("weak_areas") or [])
        missing_domains.extend(
            entry["domain"] for entry in (report.get("knowledge_coverage") or {}).get("missing_domains", [])
        )
        if report.get("failure_rate") is not None:
            failure_rates.append(report["failure_rate"])
        if report.get("hallucination_rate") is not None:
            hallucination_rates.append(report["hallucination_rate"])

    recurring_weak_domains: list[str] = []
    for session in recent_mb09:
        recurring = (session.get("knowledge_gap_evolution_report") or {}).get("recurring_weak_domains") or []
        recurring_weak_domains.extend(entry["domain"] for entry in recurring)

    research_drafts_available = sum(1 for s in recent_mb10 if s.get("dataset_draft"))
    consensus_verdicts = [
        s["consensus_report"]["verdict"] for s in recent_mb10 if (s.get("consensus_report") or {}).get("verdict")
    ]

    avg_failure_rate = round(sum(failure_rates) / len(failure_rates), 4) if failure_rates else 0.0
    avg_hallucination_rate = round(sum(hallucination_rates) / len(hallucination_rates), 4) if hallucination_rates else 0.0
    unique_weak_domains = sorted(set(weak_domains) | set(recurring_weak_domains))
    unique_missing_domains = sorted(set(missing_domains))

    advanced_overall_score = ((advanced_report.get("scores") or {}).get("overall") or {}).get("score", 0.0)

    pressure = 0.0
    pressure += min(len(unique_weak_domains) * 8.0, 40.0)
    pressure += min(len(unique_missing_domains) * 8.0, 20.0)
    pressure += min(avg_failure_rate * 100, 20.0)
    pressure += min(avg_hallucination_rate * 100, 10.0)
    if advanced_overall_score < 60.0:
        pressure += 10.0
    evolution_pressure = round(min(pressure, 100.0), 1)

    return {
        "dataset_status": dataset_training.get("status"),
        "dataset_record_count": dataset_analysis.get("records_analyzed", 0),
        "advanced_overall_score": advanced_overall_score,
        "weak_domains": unique_weak_domains,
        "missing_domains": unique_missing_domains,
        "cycles_compared": {"mb08": len(recent_mb08), "mb09": len(recent_mb09), "mb10": len(recent_mb10)},
        "average_failure_rate": avg_failure_rate,
        "average_hallucination_rate": avg_hallucination_rate,
        "research_drafts_available": research_drafts_available,
        "provider_consensus_verdicts": consensus_verdicts,
        "evolution_pressure": evolution_pressure,
    }
