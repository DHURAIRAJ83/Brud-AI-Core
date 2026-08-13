"""MB-19: Evaluation & Release Readiness Report -- pure assembly only.
Merges every earlier stage's already-computed output into the single
document the admin reviews. Never recomputes anything; every field is
a direct pass-through of an earlier stage's own real output. Always
discloses, explicitly, every honest limitation the task spec requires.
"""

from __future__ import annotations

from typing import Any


def generate_evaluation_report(
    *, session_public_id: str, topic: str, dataset_collection_report: dict[str, Any],
    rag_collection_report: dict[str, Any], package_collection_report: dict[str, Any],
    language_benchmark_report: dict[str, Any], ocr_benchmark_report: dict[str, Any],
    grounding_benchmark_report: dict[str, Any], retrieval_benchmark_report: dict[str, Any],
    multimodal_benchmark_report: dict[str, Any], package_benchmark_report: dict[str, Any],
    regression_report: dict[str, Any], score_summary: dict[str, Any], release_readiness: dict[str, Any],
) -> dict[str, Any]:
    return {
        "session_public_id": session_public_id,
        "topic": topic,
        "status": release_readiness["status"],
        "overall_score": score_summary["overall_score"],
        "category_scores": score_summary["category_scores"],
        "input_summary": {
            "dataset_count": dataset_collection_report.get("accepted_count", 0),
            "rag_session_count": rag_collection_report.get("accepted_count", 0),
            "training_package_count": package_collection_report.get("accepted_count", 0),
        },
        "language_benchmark": language_benchmark_report,
        "ocr_benchmark": ocr_benchmark_report,
        "grounding_benchmark": grounding_benchmark_report,
        "retrieval_benchmark": retrieval_benchmark_report,
        "multimodal_benchmark": multimodal_benchmark_report,
        "package_benchmark": package_benchmark_report,
        "regression": regression_report,
        "release_readiness": release_readiness,
        "blocking_issues": release_readiness["blocking_issues"],
        "no_model_inference_performed": True,
        "no_benchmark_against_real_model_outputs": True,
        "no_semantic_correctness_verification_performed": True,
        "retrieval_quality_limited_to_stored_evidence": True,
        "release_readiness_is_metadata_based": True,
        "evaluation_approval_does_not_guarantee_production_model_quality": True,
        "disclaimer": (
            "this report measures whether Mini Brain's own already-computed signals are internally "
            "consistent and traceable -- it never runs a model, never benchmarks against real model "
            "outputs, and never verifies semantic correctness; retrieval quality is limited entirely "
            "to already-stored evidence; release readiness is metadata-based and every threshold used "
            "is a fixed heuristic; evaluation approval does not guarantee production model quality"
        ),
        "ready_for_admin_review": True,
    }
