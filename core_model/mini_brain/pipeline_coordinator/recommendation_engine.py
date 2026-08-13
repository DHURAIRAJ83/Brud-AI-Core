"""MB-12: Global Recommendation Engine -- pure. Recommends exactly one
of the same nine named actions `admin_decision_center` validates,
always with WHY, cited evidence, confidence, risk, and dependencies.
Never executes anything -- the admin decides regardless of what is
recommended here.
"""

from __future__ import annotations

from typing import Any

RECOMMENDATIONS = (
    "continue", "pause", "research_more", "request_providers", "improve_dataset", "retry_rag",
    "approve_training", "reject", "archive",
)
_TRAINING_READY_STAGES = {"rag_testing", "training_candidate"}


def recommend_next_action(
    *,
    current_stage: str,
    rag_gate: dict[str, Any] | None,
    training_readiness: dict[str, Any],
    pipeline_completion_percent: float,
    remaining_steps: list[str],
) -> dict[str, Any]:
    evidence = {
        "current_stage": current_stage, "training_readiness_status": training_readiness["status"],
        "unified_readiness_score": training_readiness["unified_readiness_score"],
        "sources_available": training_readiness["sources_available"],
        "pipeline_completion_percent": pipeline_completion_percent,
        "rag_gate_passed": rag_gate["passed"] if rag_gate else None,
    }
    confidence = round(min(training_readiness["sources_available"] / training_readiness["sources_total"] * 100, 95.0), 1)

    if rag_gate is not None and not rag_gate["passed"]:
        return {
            "action": "improve_dataset",
            "why": f"the RAG gate failed ({'; '.join(rag_gate['reasons'])}) -- return to Dataset Evolution before Training",
            "evidence": evidence, "confidence": confidence, "risk": "Medium", "dependencies": remaining_steps,
        }

    if training_readiness["status"] == "Not Ready":
        return {
            "action": "improve_dataset",
            "why": f"unified training readiness score {training_readiness['unified_readiness_score']} is Not Ready",
            "evidence": evidence, "confidence": confidence, "risk": "High", "dependencies": remaining_steps,
        }

    if training_readiness["sources_available"] < training_readiness["sources_total"] / 2:
        return {
            "action": "research_more",
            "why": f"only {training_readiness['sources_available']} of {training_readiness['sources_total']} readiness sources are available yet -- too little evidence to recommend further",
            "evidence": evidence, "confidence": confidence, "risk": "Low", "dependencies": remaining_steps,
        }

    if training_readiness["status"] == "Needs Improvement":
        return {
            "action": "improve_dataset",
            "why": f"unified training readiness score {training_readiness['unified_readiness_score']} needs improvement before Training",
            "evidence": evidence, "confidence": confidence, "risk": "Medium", "dependencies": remaining_steps,
        }

    if current_stage in _TRAINING_READY_STAGES:
        return {
            "action": "approve_training",
            "why": f"training readiness is '{training_readiness['status']}' and the pipeline has reached '{current_stage}' -- ready for the admin to approve training",
            "evidence": evidence, "confidence": confidence, "risk": "Low", "dependencies": remaining_steps,
        }

    return {
        "action": "continue",
        "why": f"no blocker found at stage '{current_stage}' -- proceed with the next real step in another phase, then link it here",
        "evidence": evidence, "confidence": confidence, "risk": "Low", "dependencies": remaining_steps,
    }
