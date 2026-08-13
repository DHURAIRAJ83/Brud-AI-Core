"""MB-17: Evidence Fusion -- pure assembly only. Combines every
retrieval layer's already-scored results into one unified, structured
evidence list -- text, OCR, image metadata, caption, object labels,
bounding boxes, and knowledge-graph edges, each tagged with its page
number and document reference. No new scoring happens here; every
item's relevance score is a direct pass-through from its own
retrieval layer.
"""

from __future__ import annotations

from typing import Any


def fuse_evidence(
    *, document_source_public_id: str, text_report: dict[str, Any], ocr_report: dict[str, Any],
    image_report: dict[str, Any], object_report: dict[str, Any], graph_report: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    for result in text_report["results"]:
        items.append({
            "evidence_type": "text", "source_record_public_id": result["record_public_id"],
            "document_source_public_id": document_source_public_id, "page_number": None,
            "image_public_id": None, "object_label": None, "bounding_box": None, "graph_edge": None,
            "content_snippet": result["snippet"], "relevance_score": result["relevance_score"],
        })

    for result in ocr_report["results"]:
        items.append({
            "evidence_type": "ocr", "source_record_public_id": result["record_public_id"],
            "document_source_public_id": document_source_public_id, "page_number": None,
            "image_public_id": None, "object_label": None, "bounding_box": None, "graph_edge": None,
            "content_snippet": (result["ocr_snippet"] or "")[:500], "relevance_score": result["relevance_score"],
        })

    for result in image_report["results"]:
        items.append({
            "evidence_type": "image", "source_record_public_id": None,
            "document_source_public_id": document_source_public_id, "page_number": result["page_number"],
            "image_public_id": result["image_public_id"], "object_label": None, "bounding_box": None,
            "graph_edge": None, "content_snippet": result.get("caption") or "", "relevance_score": result["relevance_score"],
        })

    for result in object_report["results"]:
        items.append({
            "evidence_type": "object", "source_record_public_id": None,
            "document_source_public_id": document_source_public_id, "page_number": None,
            "image_public_id": None, "object_label": result["label"], "bounding_box": result.get("bounding_box"),
            "graph_edge": None, "content_snippet": result["label"], "relevance_score": result["relevance_score"],
        })

    for edge in graph_report["matched_edges"]:
        statement = f"{edge['from']} {edge['relationship']} {edge['to']}"
        items.append({
            "evidence_type": "graph_edge", "source_record_public_id": None,
            "document_source_public_id": document_source_public_id, "page_number": None,
            "image_public_id": None, "object_label": None, "bounding_box": None, "graph_edge": edge,
            "content_snippet": statement, "relevance_score": 1.0,
        })

    items.sort(key=lambda item: -item["relevance_score"])

    return {
        "evidence": items, "evidence_count": len(items),
        "counts_by_type": {
            "text": len(text_report["results"]), "ocr": len(ocr_report["results"]),
            "image": len(image_report["results"]), "object": len(object_report["results"]),
            "graph_edge": len(graph_report["matched_edges"]),
        },
    }
