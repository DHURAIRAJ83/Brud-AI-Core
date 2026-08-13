"""MB-13: OCR Correction Planner -- pure. Classifies already-computed
`core_model.corpus.tamil_normalization.normalize_tamil_text()` output
(reused unchanged, computed per record at the service layer) into a
suggestion queue. Never edits automatically -- only reports possible
OCR mistakes, a confidence band, and the suggested correction.
"""

from __future__ import annotations

from typing import Any

MAX_CORRECTIONS_STORED = 200


def plan_ocr_corrections(*, texts: list[str], normalization_results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(texts)
    ocr_substitution_records = sum(
        1 for r in normalization_results if r["transformation_counts"].get("tamil_ocr_substitutions")
    )
    zero_width_records = sum(
        1 for r in normalization_results if r["transformation_counts"].get("stray_zero_width_characters")
    )

    corrections: list[dict[str, Any]] = []
    for i, (text, result) in enumerate(zip(texts, normalization_results)):
        if result["normalized_text"] != text:
            confidence = "high" if result["transformation_counts"].get("tamil_ocr_substitutions") else "medium"
            corrections.append({
                "record_index": i, "original_preview": text[:80],
                "suggested_text_preview": result["normalized_text"][:80],
                "transformation_counts": result["transformation_counts"], "confidence": confidence,
            })

    issue_rate = (len(corrections) / total) if total else 0.0
    ocr_score = round(max(0.0, 100.0 - issue_rate * 100.0), 1)

    return {
        "records_analyzed": total,
        "ocr_substitution_record_count": ocr_substitution_records,
        "zero_width_record_count": zero_width_records,
        "possible_corrections": corrections[:MAX_CORRECTIONS_STORED],
        "possible_correction_count": len(corrections),
        "ocr_score": ocr_score,
        "auto_applied": False,
        "disclosure": (
            "every correction here is a suggestion only -- MB-13 never edits a dataset record; an "
            "admin must apply any accepted correction manually through Dataset Studio"
        ),
    }
