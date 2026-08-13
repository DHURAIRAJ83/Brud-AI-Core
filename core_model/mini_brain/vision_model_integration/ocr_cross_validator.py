"""MB-15: OCR/Vision/Dataset/Language Cross Validation -- pure.
Extends MB-14's own OCR-vs-dataset-text comparison (reused here as a
passthrough `document_dataset_status`) with a third and fourth signal:
whether the vision provider's own predicted labels textually appear
anywhere in the OCR or dataset text, and MB-13's own already-computed
language status when a language session is linked. This is a
word-overlap heuristic, not proof a label is correct or incorrect --
disclosed explicitly. Never auto-corrects anything.
"""

from __future__ import annotations

from typing import Any

DUPLICATE_LABEL_THRESHOLD = 3


def cross_validate_vision(
    *, ocr_text: str, dataset_text: str | None, vision_labels: list[str],
    document_dataset_status: str | None, language_report_status: str | None,
) -> dict[str, Any]:
    combined_text = f"{ocr_text or ''} {dataset_text or ''}".lower()
    label_counts: dict[str, int] = {}
    for label in vision_labels:
        label_counts[label] = label_counts.get(label, 0) + 1

    missing_labels = [
        label for label in sorted(set(vision_labels))
        if label.lower() not in combined_text and combined_text.strip()
    ]
    duplicate_labels = [label for label, count in label_counts.items() if count >= DUPLICATE_LABEL_THRESHOLD]

    conflict = document_dataset_status in ("conflict", "mismatch")
    if conflict:
        status = "conflict"
    elif missing_labels or duplicate_labels:
        status = "mismatch"
    elif not vision_labels:
        status = "missing"
    else:
        status = "match"

    return {
        "status": status,
        "missing_labels": missing_labels,
        "duplicate_labels": duplicate_labels,
        "document_dataset_status": document_dataset_status,
        "language_report_status": language_report_status,
        "auto_corrected": False,
        "disclosure": (
            "label/text overlap is a word-matching heuristic, not proof a predicted label is "
            "correct or that a missing label is wrong -- it flags candidates for admin review only"
        ),
    }
