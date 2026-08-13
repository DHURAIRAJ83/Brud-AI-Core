"""MB-11: Evolution Report Generator -- pure assembly only. Merges
every stage's already-computed output into the single document the
admin reviews. Never recomputes anything; every field is a direct
pass-through of an earlier stage's own real output.
"""

from __future__ import annotations

from typing import Any


def generate_evolution_report(
    *,
    session_public_id: str,
    dataset_source_public_id: str,
    evolution_analysis: dict[str, Any],
    coverage_report: dict[str, Any],
    dependency_graph: dict[str, Any],
    relationship_report: dict[str, Any],
    expansion_plan: dict[str, Any] | None,
    version_plan: dict[str, Any] | None,
    knowledge_factory_plan: dict[str, Any] | None,
    synthetic_dataset_plan: dict[str, Any] | None,
    quality_evolution: dict[str, Any] | None,
    simulation_report: dict[str, Any] | None,
    recommendation_report: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "session_public_id": session_public_id,
        "dataset_source_public_id": dataset_source_public_id,
        "dataset_summary": {
            "status": evolution_analysis.get("dataset_status"),
            "record_count": evolution_analysis.get("dataset_record_count"),
            "advanced_overall_score": evolution_analysis.get("advanced_overall_score"),
            "evolution_pressure": evolution_analysis.get("evolution_pressure"),
        },
        "coverage": coverage_report,
        "weak_areas": evolution_analysis.get("weak_domains", []),
        "strong_areas": [
            d for d, v in coverage_report.get("by_domain", {}).items() if v["classification"] == "Excellent"
        ],
        "dependency_graph": dependency_graph,
        "relationship_graph": relationship_report,
        "dataset_evolution": {"expansion_plan": expansion_plan, "version_plan": version_plan},
        "knowledge_evolution": {
            "knowledge_factory_plan": knowledge_factory_plan, "synthetic_dataset_plan": synthetic_dataset_plan,
        },
        "quality_prediction": quality_evolution,
        "training_prediction": simulation_report,
        "risk_analysis": {
            "expansion_risk": (expansion_plan or {}).get("action"),
            "version_risk": (version_plan or {}).get("risk"),
            "quality_risk": (quality_evolution or {}).get("risk"),
        },
        "recommendation": recommendation_report,
        "next_action": (recommendation_report or {}).get("recommendation"),
        "ready_for_admin_review": recommendation_report is not None,
    }
