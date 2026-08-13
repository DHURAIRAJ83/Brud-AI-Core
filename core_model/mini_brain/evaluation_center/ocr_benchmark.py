"""MB-19: OCR Benchmark -- pure. Reuses MB-14's own
`cross_validate_ocr()` unchanged, applied per already-retrieved MB-17
evidence group -- never a second OCR-comparison implementation, never
a new OCR pass.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.vision_intelligence.ocr_cross_validator import cross_validate_ocr


def run_ocr_benchmark(*, evidence_groups: list[dict[str, Any]]) -> dict[str, Any]:
    """`evidence_groups`: one entry per evaluated RAG session, each
    ``{"ocr_snippets": list[str], "text_snippets": list[str]}`` drawn
    from that session's own already-retrieved MB-17 evidence rows."""
    if not evidence_groups:
        return {
            "session_count": 0, "ocr_text_availability": None, "ocr_dataset_overlap_ratio": None,
            "ocr_conflict_ratio": None, "evaluated_count": 0,
            "disclosure": "no RAG session evidence was supplied -- OCR benchmark is honestly empty",
        }

    availability_count = 0
    overlap_ratios: list[float] = []
    conflict_count = 0
    evaluated = 0
    per_session: list[dict[str, Any]] = []

    for group in evidence_groups:
        ocr_text = " ".join(group.get("ocr_snippets") or [])
        text_snippets = group.get("text_snippets") or []
        dataset_text = " ".join(text_snippets) if text_snippets else None
        if ocr_text.strip():
            availability_count += 1
        result = cross_validate_ocr(
            ocr_text=ocr_text, dataset_text=dataset_text, language_report_status=None,
        )
        if result["status"] != "missing":
            evaluated += 1
            overlap_ratios.append(result["match_ratio"] or 0.0)
            if result["status"] == "conflict":
                conflict_count += 1
        per_session.append({"status": result["status"], "match_ratio": result["match_ratio"]})

    total = len(evidence_groups)
    return {
        "session_count": total,
        "ocr_text_availability": round(availability_count / total, 3),
        "ocr_dataset_overlap_ratio": round(sum(overlap_ratios) / len(overlap_ratios), 3) if overlap_ratios else None,
        "ocr_conflict_ratio": round(conflict_count / evaluated, 3) if evaluated else 0.0,
        "evaluated_count": evaluated,
        "per_session": per_session,
        "disclosure": (
            "ocr_conflict_ratio is computed only over sessions where both OCR and dataset text were "
            "available for comparison -- sessions with no OCR evidence at all are counted in "
            "ocr_text_availability but excluded from the conflict rate denominator, never scored as "
            "a fabricated conflict"
        ),
    }
