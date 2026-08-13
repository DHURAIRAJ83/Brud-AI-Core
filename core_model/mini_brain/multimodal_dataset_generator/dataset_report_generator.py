"""MB-16: Dataset Report -- pure assembly only. Merges every stage's
already-computed output into the single document the admin reviews.
Never recomputes anything; every field is a direct pass-through of an
earlier stage's own real output.
"""

from __future__ import annotations

from typing import Any

READY_THRESHOLD = 75.0
NEEDS_REVIEW_THRESHOLD = 40.0


def generate_dataset_report(
    *, multimodal_dataset_session_public_id: str, document_source_public_id: str,
    quality_report: dict[str, Any], record_count: int, duplicate_report: dict[str, Any],
) -> dict[str, Any]:
    overall = quality_report["overall_dataset_quality"]
    if overall >= READY_THRESHOLD:
        status = "Ready"
    elif overall >= NEEDS_REVIEW_THRESHOLD:
        status = "Needs Review"
    else:
        status = "Not Ready"

    problems: list[str] = []
    suggestions: list[str] = []
    if record_count == 0:
        problems.append("no draft records were generated")
        suggestions.append("link at least a Language Intelligence or Vision Intelligence session before certifying")
    if duplicate_report["exact_duplicate_count"] or duplicate_report["normalized_duplicate_count"]:
        problems.append(
            f"{duplicate_report['exact_duplicate_count']} exact and {duplicate_report['normalized_duplicate_count']} "
            "normalized duplicate record(s) detected"
        )
        suggestions.append("review and remove duplicate records before certifying")

    return {
        "multimodal_dataset_session_public_id": multimodal_dataset_session_public_id,
        "document_source_public_id": document_source_public_id,
        "status": status, "overall_dataset_quality": overall, "components": quality_report["components"],
        "record_count": record_count, "problems": problems, "suggestions": suggestions,
        "recommendation": "approve" if status == "Ready" else "request_changes",
        "risk": "Low" if status == "Ready" else "Medium" if status == "Needs Review" else "High",
        "ready_for_admin_review": True,
    }
