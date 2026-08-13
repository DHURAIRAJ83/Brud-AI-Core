"""MB-14: OCR Cross Validation -- pure. Compares a document page's
real OCR text (already extracted by Document Workspace's own existing
pipeline) against a linked Dataset Studio record's real text, when
one is supplied. The "Image" side of the spec's own comparison chain
is honestly absent here -- no vision model exists to describe image
content for comparison (see `vision_understanding.py`) -- so this
module compares what is actually available: OCR text, dataset text,
and (optionally) MB-13's own already-computed Language Intelligence
status. Never auto-corrects anything.
"""

from __future__ import annotations

from typing import Any

MATCH_THRESHOLD = 0.7
MISMATCH_THRESHOLD = 0.3


def cross_validate_ocr(
    *, ocr_text: str, dataset_text: str | None, language_report_status: str | None,
) -> dict[str, Any]:
    ocr_text = ocr_text or ""
    if not ocr_text.strip():
        return {
            "status": "missing", "reason": "no OCR text available for this page", "match_ratio": None,
            "auto_corrected": False,
        }
    if dataset_text is None:
        return {
            "status": "missing", "reason": "no linked dataset text supplied for comparison",
            "match_ratio": None, "auto_corrected": False,
        }

    ocr_words = set(ocr_text.lower().split())
    dataset_words = set((dataset_text or "").lower().split())
    if not ocr_words and not dataset_words:
        return {"status": "missing", "reason": "both texts are empty", "match_ratio": 0.0, "auto_corrected": False}

    union = len(ocr_words | dataset_words) or 1
    match_ratio = round(len(ocr_words & dataset_words) / union, 3)

    if match_ratio >= MATCH_THRESHOLD:
        status = "match"
    elif match_ratio >= MISMATCH_THRESHOLD:
        status = "mismatch"
    else:
        status = "conflict"

    return {
        "status": status, "match_ratio": match_ratio, "ocr_word_count": len(ocr_words),
        "dataset_word_count": len(dataset_words), "language_intelligence_status": language_report_status,
        "auto_corrected": False,
    }
