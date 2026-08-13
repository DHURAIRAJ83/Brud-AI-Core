"""MB-14: Vision Report -- pure assembly only. Merges every stage's
already-computed output into the single document the admin reviews:
Problems, Suggestions, Missing Objects, Confidence, Risk, Admin
Recommendation, Ready/Needs Review/Not Ready. Never recomputes
anything; every field is a direct pass-through of an earlier stage's
own real output.
"""

from __future__ import annotations

from typing import Any

READY_THRESHOLD = 75.0
NEEDS_REVIEW_THRESHOLD = 40.0


def generate_vision_report(
    *,
    session_public_id: str,
    document_source_public_id: str,
    quality_score_report: dict[str, Any],
    unknown_object_count: int,
    ocr_status_counts: dict[str, int],
) -> dict[str, Any]:
    overall = quality_score_report["overall_vision_score"]
    if overall >= READY_THRESHOLD:
        status = "Ready"
    elif overall >= NEEDS_REVIEW_THRESHOLD:
        status = "Needs Review"
    else:
        status = "Not Ready"

    problems: list[str] = []
    suggestions: list[str] = []
    if unknown_object_count:
        problems.append(f"{unknown_object_count} object(s) still Unknown -- pending admin annotation")
        suggestions.append("review and annotate the remaining Unknown Object placeholders")
    if ocr_status_counts.get("conflict"):
        problems.append(f"{ocr_status_counts['conflict']} page(s) with OCR/dataset text conflict")
        suggestions.append("resolve OCR/dataset text conflicts before certifying")
    if ocr_status_counts.get("missing"):
        problems.append(f"{ocr_status_counts['missing']} page(s) missing comparable text")

    return {
        "session_public_id": session_public_id, "document_source_public_id": document_source_public_id,
        "status": status, "overall_vision_score": overall, "components": quality_score_report["components"],
        "problems": problems, "suggestions": suggestions, "missing_objects": unknown_object_count,
        "confidence": overall, "risk": "Low" if status == "Ready" else "Medium" if status == "Needs Review" else "High",
        "recommendation": "approve" if status == "Ready" else "request_fix",
        "ready_for_admin_review": True,
    }
