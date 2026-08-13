"""MB-20: Release Readiness Report -- pure assembly only. Merges every
earlier stage's already-computed output into the single document the
admin reviews. Never recomputes anything; every field is a direct
pass-through of an earlier stage's own real output. Always discloses,
explicitly, every honest limitation the task spec requires.
"""

from __future__ import annotations

from typing import Any


def _component_score(status: str | None, mapping: dict[str, float]) -> float | None:
    if status is None:
        return None
    return mapping.get(status)


def generate_release_report(
    *, session_public_id: str, topic: str, dataset_collection_report: dict[str, Any],
    rag_collection_report: dict[str, Any], training_package_collection_report: dict[str, Any],
    evaluation_collection_report: dict[str, Any], safety_gate_report: dict[str, Any],
    compliance_gate_report: dict[str, Any], benchmark_gate_report: dict[str, Any],
    risk_register: dict[str, Any], rollback_plan: dict[str, Any], compatibility_matrix: dict[str, Any],
    deployment_prerequisites: dict[str, Any], operator_instructions: dict[str, Any],
    release_decision: dict[str, Any], reproducibility_record: dict[str, Any],
) -> dict[str, Any]:
    safety_score = _component_score(safety_gate_report.get("overall_status"), {"pass": 100.0, "fail": 0.0})
    compliance_score = _component_score(
        compliance_gate_report.get("overall_status"), {"complete": 100.0, "in_progress": 50.0, "fail": 0.0},
    )
    benchmark_score = _component_score(
        benchmark_gate_report.get("overall_benchmark_status"),
        {"pass": 100.0, "marginal": 60.0, "fail": 0.0, "no_data": 50.0},
    )
    component_scores = {"safety": safety_score, "compliance": compliance_score, "benchmark": benchmark_score}
    available = [v for v in component_scores.values() if v is not None]
    overall_readiness_score = round(sum(available) / len(available), 1) if available else None

    blocking_issues = list(release_decision.get("blocking_issues", []))

    return {
        "session_public_id": session_public_id, "topic": topic,
        "final_recommendation": release_decision.get("recommendation"),
        "overall_readiness_score": overall_readiness_score, "component_scores": component_scores,
        "source_evidence_summary": {
            "dataset_count": dataset_collection_report.get("accepted_count", 0),
            "rag_session_count": rag_collection_report.get("accepted_count", 0),
            "training_package_accepted": training_package_collection_report.get("accepted", False),
            "evaluation_accepted": evaluation_collection_report.get("accepted", False),
        },
        "safety_status": safety_gate_report.get("overall_status"), "safety_gates": safety_gate_report,
        "compliance_status": compliance_gate_report.get("overall_status"), "compliance_gates": compliance_gate_report,
        "benchmark_status": benchmark_gate_report.get("overall_benchmark_status"), "benchmark_gates": benchmark_gate_report,
        "risk_summary": {
            "entry_count": risk_register.get("entry_count", 0),
            "severity_counts": risk_register.get("severity_counts", {}),
        },
        "risk_register": risk_register,
        "rollback_readiness": {
            "trigger_condition_count": len(rollback_plan.get("trigger_conditions", [])),
            "step_count": len(rollback_plan.get("rollback_steps", [])),
            "executed": rollback_plan.get("executed", False),
        },
        "rollback_plan": rollback_plan,
        "compatibility_summary": compatibility_matrix,
        "deployment_prerequisites": deployment_prerequisites,
        "operator_checklist": operator_instructions,
        "reproducibility": reproducibility_record,
        "blocking_issues": blocking_issues,
        "no_deployment_performed": True,
        "no_runtime_started": True,
        "no_public_traffic_enabled": True,
        "no_inference_benchmark_executed": True,
        "thresholds_are_heuristic_governance_rules": True,
        "compliance_is_checklist_based_not_legal_certification": True,
        "approval_does_not_imply_production_safety": True,
        "rollback_plan_is_procedural_not_executable_automation": True,
        "disclaimer": (
            "no deployment has occurred, no runtime has been started, and no public traffic has been "
            "enabled by this phase or any phase before it in this chain; this report measures "
            "governance readiness only -- approval here does not imply production safety, and the "
            "rollback plan is a procedural document, never executable automation"
        ),
        "ready_for_admin_review": True,
    }
