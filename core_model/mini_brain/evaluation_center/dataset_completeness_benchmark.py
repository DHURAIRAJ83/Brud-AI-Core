"""MB-19: Dataset Completeness Benchmark -- pure. Aggregates MB-16's
own already-computed quality and duplicate reports across every
collected dataset session -- never re-scores quality or re-runs
duplicate detection itself.
"""

from __future__ import annotations

from typing import Any


def analyze_dataset_completeness(*, dataset_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """`dataset_sessions`: one entry per collected MB-16 session, each
    ``{"quality_report": dict, "duplicate_report": dict, "record_count": int}``."""
    if not dataset_sessions:
        return {
            "dataset_count": 0, "total_record_count": 0, "average_dataset_quality": None,
            "total_exact_duplicate_count": 0,
            "disclosure": "no MB-16 dataset session was supplied -- completeness is honestly unavailable",
        }

    quality_scores = [
        session["quality_report"]["overall_dataset_quality"] for session in dataset_sessions
        if session.get("quality_report", {}).get("overall_dataset_quality") is not None
    ]
    duplicate_total = sum(
        session.get("duplicate_report", {}).get("exact_duplicate_count", 0) for session in dataset_sessions
    )
    total_records = sum(session.get("record_count", 0) for session in dataset_sessions)

    return {
        "dataset_count": len(dataset_sessions),
        "total_record_count": total_records,
        "average_dataset_quality": round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else None,
        "total_exact_duplicate_count": duplicate_total,
        "disclosure": (
            "quality and duplicate figures are read directly from MB-16's own already-computed "
            "session reports, never recomputed here"
        ),
    }
