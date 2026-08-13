"""MB-09: Admin Planning Report -- pure assembly only. Merges every
stage's already-computed output into the single document the admin
reviews. Never recomputes anything; every field is a direct
pass-through of an earlier stage's own real output, so nothing here
can fabricate evidence the earlier stages didn't already produce.
"""

from __future__ import annotations

from typing import Any


def generate_planning_report(
    *,
    session_public_id: str,
    memory_entry_count: int,
    knowledge_gap_evolution_report: dict[str, Any],
    learning_queue_report: dict[str, Any],
    draft_report: dict[str, Any] | None,
    provider_consensus_report: dict[str, Any] | None,
    dataset_evolution_report: dict[str, Any] | None,
    roadmap_report: dict[str, Any],
    recommendation_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "session_public_id": session_public_id,
        "learning_history": {"cycles_in_memory": memory_entry_count},
        "knowledge_gap_summary": {
            "cycles_compared": knowledge_gap_evolution_report["cycles_compared"],
            "unresolved_knowledge_gaps": knowledge_gap_evolution_report["unresolved_knowledge_gaps"],
            "recurring_failures_detected": knowledge_gap_evolution_report["recurring_failures_detected"],
            "recurring_hallucinations_detected": knowledge_gap_evolution_report["recurring_hallucinations_detected"],
        },
        "weak_domain_ranking": knowledge_gap_evolution_report["recurring_weak_domains"],
        "learning_queue": learning_queue_report["queue"],
        "draft_suggestions": draft_report,
        "provider_consensus_recommendation": provider_consensus_report,
        "dataset_evolution_plan": dataset_evolution_report,
        "roadmap": roadmap_report,
        "next_action": recommendation_report,
    }
