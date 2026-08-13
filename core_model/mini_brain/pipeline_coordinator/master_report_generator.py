"""MB-12: Master Pipeline Report -- pure assembly only. Merges every
stage's already-computed output into the single document the admin
reviews. Never recomputes anything; every field is a direct
pass-through of an earlier stage's own real output.
"""

from __future__ import annotations

from typing import Any


def generate_master_report(
    *,
    session_public_id: str,
    topic: str,
    current_stage: str,
    pipeline_manager_report: dict[str, Any],
    rag_first_report: dict[str, Any] | None,
    training_readiness_report: dict[str, Any],
    recommendation_report: dict[str, Any] | None,
    dataset_health_score: float | None,
) -> dict[str, Any]:
    risks: list[str] = []
    if rag_first_report and not rag_first_report["passed"]:
        risks.extend(rag_first_report["reasons"])
    if training_readiness_report["status"] != "Ready":
        risks.append(f"training readiness is '{training_readiness_report['status']}'")
    if pipeline_manager_report["completion_percent"] < 50.0:
        risks.append(f"pipeline is only {pipeline_manager_report['completion_percent']}% complete")

    return {
        "session_public_id": session_public_id,
        "topic": topic,
        "current_stage": current_stage,
        "pipeline_health": {
            "completion_percent": pipeline_manager_report["completion_percent"],
            "completed_steps": pipeline_manager_report["completed_steps"],
            "remaining_steps": pipeline_manager_report["remaining_steps"],
        },
        "knowledge_health": {
            "research_done": "research" in pipeline_manager_report["completed_steps"],
            "provider_consensus_done": "provider_consensus" in pipeline_manager_report["completed_steps"],
        },
        "dataset_health": {"score": dataset_health_score},
        "rag_health": rag_first_report,
        "training_readiness": training_readiness_report,
        "benchmark_readiness": current_stage in {"benchmark_ready", "release_candidate", "completed"},
        "release_readiness": current_stage in {"release_candidate", "completed"},
        "risks": risks,
        "recommendation": recommendation_report,
        "next_action": (recommendation_report or {}).get("action"),
        "ready_for_admin_review": recommendation_report is not None,
    }
