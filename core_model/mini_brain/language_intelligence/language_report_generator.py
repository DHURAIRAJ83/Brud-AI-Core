"""MB-13: Language Report Generator -- pure assembly only. Merges
every stage's already-computed output into the single document the
admin reviews: Language Health, Problems, Corrections, Confidence,
Recommendations, Risk, Ready/Not Ready. Never recomputes anything;
every field is a direct pass-through of an earlier stage's own real
output.
"""

from __future__ import annotations

from typing import Any

READY_THRESHOLD = 75.0
MAX_CORRECTIONS_SHOWN = 20


def generate_language_report(
    *,
    session_public_id: str,
    dataset_source_public_id: str,
    unicode_report: dict[str, Any],
    character_report: dict[str, Any],
    spell_report: dict[str, Any],
    ocr_report: dict[str, Any],
    sentence_quality_report: dict[str, Any],
    dataset_draft_report: dict[str, Any],
    quality_score_report: dict[str, Any],
) -> dict[str, Any]:
    overall = quality_score_report["overall_language_quality"]
    ready = overall >= READY_THRESHOLD

    problems: list[str] = []
    if unicode_report.get("flagged_record_count"):
        problems.append(f"{unicode_report['flagged_record_count']} record(s) with Unicode issues")
    if character_report.get("flagged_record_count"):
        problems.append(f"{character_report['flagged_record_count']} record(s) with broken Tamil script sequences")
    if spell_report.get("affected_record_count"):
        problems.append(f"{spell_report['affected_record_count']} record(s) with known spelling issues")
    if ocr_report.get("possible_correction_count"):
        problems.append(f"{ocr_report['possible_correction_count']} possible OCR correction(s)")
    if sentence_quality_report.get("duplicate_record_count"):
        problems.append(f"{sentence_quality_report['duplicate_record_count']} duplicate record(s)")

    corrections = (
        list(ocr_report.get("possible_corrections", []))[:MAX_CORRECTIONS_SHOWN]
        + list(spell_report.get("matches", []))[:MAX_CORRECTIONS_SHOWN]
    )

    return {
        "session_public_id": session_public_id,
        "dataset_source_public_id": dataset_source_public_id,
        "language_health": {"overall_language_quality": overall, "components": quality_score_report["components"]},
        "problems": problems,
        "problem_count": len(problems),
        "corrections_suggested": corrections,
        "confidence": overall,
        "recommendation": "approve" if ready else "request_fix",
        "risk": "Low" if ready else "Medium" if overall >= 50.0 else "High",
        "ready": ready,
        "status": "Ready" if ready else "Not Ready",
        "dataset_draft_available": bool(dataset_draft_report.get("applicable")),
        "ready_for_admin_review": True,
    }
