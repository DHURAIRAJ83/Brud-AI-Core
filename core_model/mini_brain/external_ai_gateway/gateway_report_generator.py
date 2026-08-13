"""MB-21: Gateway Evaluation Report -- pure assembly only. Merges every
earlier stage's already-computed output into the single document the
admin reviews. Never recomputes anything; every field is a direct
pass-through of an earlier stage's own real output. Always discloses,
explicitly, every honest limitation the task spec requires.
"""

from __future__ import annotations

from typing import Any


def generate_gateway_report(
    *, session_public_id: str, topic: str, purpose: str, provider_runs: list[dict[str, Any]],
    agreement_report: dict[str, Any], failure_report: dict[str, Any], safety_report: dict[str, Any],
    scoring_report: dict[str, Any], recommendations: dict[str, Any], privacy_audit: dict[str, Any],
) -> dict[str, Any]:
    success_matrix = [
        {"provider_key": run["provider_key"], "status": run["status"], "latency_ms": run.get("latency_ms")}
        for run in provider_runs
    ]

    key_findings: list[str] = []
    if agreement_report["contradiction_count"] > 0:
        key_findings.append(f"{agreement_report['contradiction_count']} low-agreement response pair(s) detected")
    if safety_report["has_violations"]:
        key_findings.append(f"{safety_report['flagged_count']} response(s) flagged for safety review")
    if failure_report["all_providers_failed"]:
        key_findings.append("all dispatched providers failed or were unavailable")
    if not key_findings:
        key_findings.append("no contradictions or safety flags were detected in this run")

    missing_knowledge = recommendations.get("missing_knowledge_topics", [])

    return {
        "session_public_id": session_public_id, "topic": topic, "purpose": purpose,
        "providers_used": [run["provider_key"] for run in provider_runs],
        "provider_success_matrix": success_matrix,
        "agreement_summary": agreement_report,
        "key_findings": key_findings,
        "missing_knowledge": missing_knowledge,
        "recommended_next_actions": (
            recommendations.get("suggested_dataset_improvements", []) + recommendations.get("suggested_rag_improvements", [])
            if purpose == "public_style_stress_test" else recommendations.get("next_actions", [])
        ),
        "confidence_level": scoring_report["confidence_level"],
        "safety_observations": safety_report,
        "privacy_audit_summary": privacy_audit,
        "external_ai_output_unverified": True,
        "no_automatic_truth_determination": True,
        "no_automatic_dataset_insertion": True,
        "no_automatic_training": True,
        "no_automatic_release_approval": True,
        "provider_availability_may_change": True,
        "provider_answers_may_be_wrong": True,
        "agreement_does_not_imply_correctness": True,
        "disclaimer": (
            "every provider output in this report is unverified candidate evidence -- no automatic "
            "truth determination, dataset insertion, training, or release approval has occurred or "
            "ever will occur as a result of this phase; provider availability and answers may both be "
            "wrong or may change at any time; agreement between providers never implies correctness"
        ),
        "ready_for_admin_review": True,
    }
