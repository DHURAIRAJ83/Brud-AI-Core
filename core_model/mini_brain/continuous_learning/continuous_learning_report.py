"""MB-08: Continuous Learning Report -- pure assembly only. Merges
every stage's already-computed report into the single structured
document the admin reviews. Never recomputes anything; every field
here is a direct pass-through or simple derivation of an earlier
stage's own real output.
"""

from __future__ import annotations

from typing import Any

HEALTHY_FAILURE_RATE = 0.10
HEALTHY_HALLUCINATION_RATE = 0.10


def _overall_health(failure_rate: float | None, hallucination_rate: float | None, weak_topic_count: int) -> str:
    failure_rate = failure_rate or 0.0
    hallucination_rate = hallucination_rate or 0.0
    if failure_rate <= HEALTHY_FAILURE_RATE and hallucination_rate <= HEALTHY_HALLUCINATION_RATE and weak_topic_count == 0:
        return "Healthy"
    if failure_rate >= 0.35 or hallucination_rate >= 0.30 or weak_topic_count >= 3:
        return "At Risk"
    return "Needs Attention"


def generate_continuous_learning_report(
    *,
    session_public_id: str,
    feedback_report: dict[str, Any],
    failure_report: dict[str, Any],
    hallucination_report: dict[str, Any],
    knowledge_gap_report: dict[str, Any],
    weak_topic_report: dict[str, Any],
    difficulty_report: dict[str, Any],
    dataset_recommendation_report: dict[str, Any],
    training_recommendation: dict[str, Any],
) -> dict[str, Any]:
    weak_topics = weak_topic_report["weak_topics"]
    overall_health = _overall_health(
        failure_report["failure_rate"], hallucination_report["hallucination_rate"], len(weak_topics),
    )

    improvement_plan: list[str] = []
    if dataset_recommendation_report["domains_needing_data"]:
        improvement_plan.append(
            f"Collect data for {len(dataset_recommendation_report['domains_needing_data'])} "
            f"weak domain(s): {', '.join(dataset_recommendation_report['domains_needing_data'][:5])}"
        )
    if training_recommendation["action"] != "No Training":
        improvement_plan.append(f"{training_recommendation['action']} -- {training_recommendation['why']}")
    if not improvement_plan:
        improvement_plan.append("No action recommended this cycle -- observed metrics are within healthy thresholds")

    return {
        "session_public_id": session_public_id,
        "overall_health": overall_health,
        "weak_areas": weak_topics,
        "strong_areas": weak_topic_report["strong_topics"],
        "knowledge_coverage": {
            "total_knowledge_gap_cases": knowledge_gap_report["total_knowledge_gap_cases"],
            "missing_domains": knowledge_gap_report["missing_domains"],
            "missing_documentation_count": knowledge_gap_report["missing_documentation_count"],
            "missing_workflow_count": knowledge_gap_report["missing_workflow_count"],
        },
        "failure_rate": failure_report["failure_rate"],
        "failure_breakdown": failure_report["failure_counts"],
        "hallucination_rate": hallucination_report["hallucination_rate"],
        "hallucination_breakdown": {
            "unsupported_claim_count": hallucination_report["unsupported_claim_count"],
            "missing_citation_count": hallucination_report["missing_citation_count"],
            "inconsistent_answer_count": hallucination_report["inconsistent_answer_count"],
        },
        "difficulty_distribution": difficulty_report["distribution"],
        "dataset_suggestions": dataset_recommendation_report["recommendations"],
        "training_suggestion": training_recommendation,
        "improvement_plan": improvement_plan,
        "feedback_summary": feedback_report,
    }
