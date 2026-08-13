"""MB-15: Vision Model Report -- pure assembly only. Merges every
stage's already-computed output into the single document the admin
reviews: Problems, Missing Objects, Conflicts, Suggestions,
Corrections, Approved Objects, Rejected Objects, Final Quality,
Recommendation. Never recomputes anything; every field is a direct
pass-through of an earlier stage's own real output.
"""

from __future__ import annotations

from typing import Any

READY_THRESHOLD = 75.0
NEEDS_REVIEW_THRESHOLD = 40.0


def generate_vision_model_report(
    *, vision_model_session_public_id: str, vision_session_public_id: str,
    quality_score_report: dict[str, Any], approved_count: int, rejected_count: int,
    corrected_count: int, missing_labels: list[str], conflicts: list[str],
) -> dict[str, Any]:
    overall = quality_score_report["overall_vision_model_score"]
    if overall >= READY_THRESHOLD:
        status = "Ready"
    elif overall >= NEEDS_REVIEW_THRESHOLD:
        status = "Needs Review"
    else:
        status = "Not Ready"

    problems: list[str] = []
    suggestions: list[str] = []
    if missing_labels:
        problems.append(f"{len(missing_labels)} predicted label(s) not found in any linked text")
        suggestions.append("review predicted labels with no textual corroboration before certifying")
    if conflicts:
        problems.append(f"{len(conflicts)} cross-validation conflict(s) detected")
        suggestions.append("resolve OCR/vision/dataset conflicts before certifying")
    if rejected_count:
        problems.append(f"{rejected_count} prediction(s) rejected or deleted by an admin")

    return {
        "vision_model_session_public_id": vision_model_session_public_id,
        "vision_session_public_id": vision_session_public_id,
        "status": status, "overall_vision_model_score": overall,
        "components": quality_score_report["components"],
        "problems": problems, "missing_objects": missing_labels, "conflicts": conflicts,
        "suggestions": suggestions, "approved_objects": approved_count, "rejected_objects": rejected_count,
        "corrected_objects": corrected_count, "final_quality": overall,
        "recommendation": "approve" if status == "Ready" else "request_fix",
        "risk": "Low" if status == "Ready" else "Medium" if status == "Needs Review" else "High",
        "ready_for_admin_review": True,
    }
