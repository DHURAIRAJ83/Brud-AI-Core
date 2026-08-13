"""MB-14: Vision Dataset Draft -- pure assembly only. Prepares image
metadata, OCR, caption, bounding boxes, objects, QA, and the knowledge
graph into one draft. Nothing here is inserted into Dataset Studio --
always `verified: false`.
"""

from __future__ import annotations

from typing import Any


def build_vision_dataset_draft(
    *,
    image_metadata: list[dict[str, Any]],
    ocr_text: str,
    caption_report: dict[str, Any],
    bounding_box_report: dict[str, Any],
    objects: list[dict[str, Any]],
    qa_report: dict[str, Any],
    knowledge_graph_report: dict[str, Any],
) -> dict[str, Any]:
    return {
        "image_metadata": image_metadata,
        "ocr_text": ocr_text,
        "caption": caption_report,
        "bounding_boxes": bounding_box_report,
        "objects": objects,
        "qa": qa_report,
        "knowledge_graph": knowledge_graph_report,
        "verified": False,
        "status": "needs_admin_review",
        "disclosure": "draft only -- nothing has been inserted into Dataset Studio; that remains the only place a dataset is actually written, and only after explicit admin approval",
    }
