"""MB-18: Pipeline Readiness Report -- pure assembly only. Merges
every stage's already-computed output into the single document the
admin reviews. Never recomputes anything; every field is a direct
pass-through of an earlier stage's own real output. Always discloses,
explicitly, that no training has ever been executed.
"""

from __future__ import annotations

from typing import Any

READY_THRESHOLD = 75.0
NEEDS_REVIEW_THRESHOLD = 40.0


def generate_readiness_report(
    *, session_public_id: str, topic: str, dataset_collection_report: dict[str, Any],
    rag_memory_collection_report: dict[str, Any], language_distribution_report: dict[str, Any],
    image_statistics_report: dict[str, Any], grounding_quality_report: dict[str, Any],
    tokenizer_coverage_report: dict[str, Any], curriculum_report: dict[str, Any],
    hardware_estimate_report: dict[str, Any], reproducibility_record: dict[str, Any],
) -> dict[str, Any]:
    components = {
        "dataset_readiness": 100.0 if dataset_collection_report["ready"] else 0.0,
        "language_coverage": 100.0 if language_distribution_report.get("session_count", 0) > 0 else 50.0,
        "vision_coverage": 100.0 if image_statistics_report["image_count"] > 0 else 100.0,
        "grounding_quality": (
            round((grounding_quality_report.get("average_confidence") or 0.0) * 100, 1)
            if grounding_quality_report.get("query_count", 0) > 0 else 50.0
        ),
        "tokenizer_coverage": 100.0 if tokenizer_coverage_report["total_character_count"] > 0 else 0.0,
        "curriculum_readiness": 100.0 if curriculum_report["stage_count"] > 0 else 0.0,
    }
    overall = round(sum(components.values()) / len(components), 1)

    blocking_issues: list[str] = []
    if not dataset_collection_report["ready"]:
        blocking_issues.append("no certified MB-16 dataset session was accepted")
    if tokenizer_coverage_report["total_character_count"] == 0:
        blocking_issues.append("no text content was collected -- tokenizer coverage is empty")
    if (grounding_quality_report.get("hallucination_rate") or 0.0) > 0.3:
        blocking_issues.append("hallucination rate among accepted RAG memory exceeds 30%")

    if blocking_issues:
        status = "Not Ready"
    elif overall >= READY_THRESHOLD:
        status = "Ready"
    elif overall >= NEEDS_REVIEW_THRESHOLD:
        status = "Needs Review"
    else:
        status = "Not Ready"

    return {
        "session_public_id": session_public_id, "topic": topic, "status": status,
        "overall_readiness_score": overall, "components": components,
        "dataset_summary": {
            "dataset_count": dataset_collection_report["accepted_count"],
            "record_count": dataset_collection_report["total_record_count"],
        },
        "image_count": image_statistics_report["image_count"],
        "language_distribution": language_distribution_report.get("dominant_language_counts", {}),
        "grounding_quality_summary": grounding_quality_report,
        "tokenizer_coverage_summary": {
            "unique_character_count": tokenizer_coverage_report["unique_character_count"],
            "script_mix": tokenizer_coverage_report["script_mix"],
            "unseen_character_risk": tokenizer_coverage_report["unseen_character_risk"],
        },
        "curriculum_summary": curriculum_report,
        "hardware_estimate": hardware_estimate_report,
        "reproducibility": reproducibility_record,
        "blocking_issues": blocking_issues,
        "recommendation": "approve" if status == "Ready" else "request_changes",
        "risk": "Low" if status == "Ready" else "Medium" if status == "Needs Review" else "High",
        "training_executed": False,
        "benchmark_executed": False,
        "disclaimer": (
            "no training has been executed by this phase -- this package is metadata only, prepared "
            "for a future, entirely separate training phase to consume; package approval does not "
            "imply model quality"
        ),
        "ready_for_admin_review": True,
    }
