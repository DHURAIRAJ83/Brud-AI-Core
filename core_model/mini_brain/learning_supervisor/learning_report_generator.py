"""MB-06: Learning Report Generator -- pure assembly only. Merges
already-computed stage reports into the single structured document
Stage 13 hands to the admin. Never recomputes anything; every field
here is a direct pass-through of an earlier stage's own real output.
"""

from __future__ import annotations

from typing import Any


def generate_learning_report(
    *,
    session_public_id: str,
    dataset_report: dict[str, Any] | None,
    rag_report: dict[str, Any] | None,
    training_report: dict[str, Any] | None,
    benchmark_report: dict[str, Any] | None,
    comparison_report: dict[str, Any] | None,
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    sections_present = {
        "dataset_report": dataset_report is not None,
        "rag_report": rag_report is not None,
        "training_report": training_report is not None,
        "benchmark_report": benchmark_report is not None,
        "comparison_report": comparison_report is not None,
    }
    high_confidence_blocking = [
        rec for rec in recommendations
        if rec["confidence"] == "high" and rec["action"] != "Safe for release review"
    ]

    return {
        "session_public_id": session_public_id,
        "sections_present": sections_present,
        "dataset_report": dataset_report,
        "rag_report": rag_report,
        "training_report": training_report,
        "benchmark_report": benchmark_report,
        "comparison_report": comparison_report,
        "recommendations": recommendations,
        "has_high_confidence_blocking_findings": bool(high_confidence_blocking),
        "blocking_recommendation_count": len(high_confidence_blocking),
    }
