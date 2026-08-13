"""MB-11: Evolution Recommendation Engine -- pure. Recommends exactly
one of the task spec's eight named next actions from already-computed
signals, always with WHY, cited evidence, confidence, and risk. Never
executes anything -- the admin decides regardless of what is
recommended here.
"""

from __future__ import annotations

from typing import Any

RECOMMENDATIONS = (
    "continue_current_dataset", "expand_dataset", "split_dataset", "replace_dataset",
    "research_more", "collect_more_data", "wait", "reject",
)
_EXPAND_ACTIONS = {"extend", "merge", "create_new"}
LOW_CONFIDENCE_THRESHOLD = 40.0
LOW_IMPROVEMENT_THRESHOLD = 5.0
LOW_PRESSURE_THRESHOLD = 5.0


def recommend_evolution(
    *,
    evolution_pressure: float,
    expansion_action: str,
    coverage_summary: dict[str, Any],
    relationship_report: dict[str, Any],
    simulation: dict[str, Any],
    risk: str,
) -> dict[str, Any]:
    evidence = {
        "evolution_pressure": evolution_pressure, "expansion_action": expansion_action,
        "critical_gap_count": coverage_summary["critical_gap_count"],
        "missing_evidence_count": len(relationship_report["missing_evidence"]),
        "conflicting_knowledge_count": relationship_report["conflicting_knowledge_count"],
        "simulation_confidence": simulation["confidence"],
        "expected_improvement": simulation["expected_improvement"],
    }
    confidence = simulation["confidence"]

    if relationship_report["conflicting_knowledge_count"] > 0:
        return {
            "recommendation": "research_more",
            "why": f"{relationship_report['conflicting_knowledge_count']} conflicting knowledge signal(s) across MB-08/MB-09/MB-10 -- resolve the disagreement before planning further",
            "evidence": evidence, "confidence": confidence, "risk": risk,
        }

    if relationship_report["missing_evidence"] and evolution_pressure > 0:
        return {
            "recommendation": "collect_more_data",
            "why": f"{len(relationship_report['missing_evidence'])} weak domain(s) have no supporting research draft yet -- more evidence is needed before committing to a plan",
            "evidence": evidence, "confidence": confidence, "risk": risk,
        }

    if confidence < LOW_CONFIDENCE_THRESHOLD and simulation["expected_improvement"] < LOW_IMPROVEMENT_THRESHOLD:
        return {
            "recommendation": "reject",
            "why": f"confidence {confidence} is below {LOW_CONFIDENCE_THRESHOLD} and expected improvement {simulation['expected_improvement']} is below {LOW_IMPROVEMENT_THRESHOLD} -- this cycle's plan is not worth acting on",
            "evidence": evidence, "confidence": confidence, "risk": risk,
        }

    if evolution_pressure < LOW_PRESSURE_THRESHOLD and coverage_summary["critical_gap_count"] == 0:
        return {
            "recommendation": "continue_current_dataset",
            "why": f"evolution pressure {evolution_pressure} is below {LOW_PRESSURE_THRESHOLD} with no critical gaps -- the current dataset needs no change this cycle",
            "evidence": evidence, "confidence": confidence, "risk": risk,
        }

    if expansion_action == "archive":
        return {
            "recommendation": "wait",
            "why": "the Expansion Planner found the dataset stagnant but not urgently needed -- wait rather than invest now",
            "evidence": evidence, "confidence": confidence, "risk": risk,
        }

    if expansion_action == "replace":
        return {
            "recommendation": "replace_dataset",
            "why": "the Expansion Planner found the dataset too degraded to extend -- replacing is the recommended path",
            "evidence": evidence, "confidence": confidence, "risk": risk,
        }

    if expansion_action == "split":
        return {
            "recommendation": "split_dataset",
            "why": "the Expansion Planner found the dataset large with no coverage gaps -- splitting into focused subsets is recommended",
            "evidence": evidence, "confidence": confidence, "risk": risk,
        }

    if expansion_action in _EXPAND_ACTIONS:
        return {
            "recommendation": "expand_dataset",
            "why": f"the Expansion Planner recommends '{expansion_action}' -- rolled up to Expand Dataset for the admin decision",
            "evidence": evidence, "confidence": confidence, "risk": risk,
        }

    return {
        "recommendation": "continue_current_dataset",
        "why": "no signal reached any other threshold -- default to no change",
        "evidence": evidence, "confidence": confidence, "risk": risk,
    }
