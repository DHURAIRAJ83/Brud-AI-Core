"""MB-16: Conversation Builder -- pure. Builds User/Assistant turns
only from real, already-computed data -- MB-14's own QA questions
(never regenerated here) and the real OCR text. No language-generation
model exists anywhere in this codebase, so nothing here invents a
question or an answer; every turn is traceable to a specific upstream
field. Always `verified: false`.
"""

from __future__ import annotations

from typing import Any

OCR_ANSWER_MAX_CHARS = 4000


def build_conversations(
    *, merged_metadata: dict[str, Any], qa_items: list[dict[str, Any]], document_source_public_id: str,
) -> dict[str, Any]:
    conversations: list[dict[str, Any]] = []
    knowledge_graph = merged_metadata["knowledge_graph"]
    image_ids = [img["public_id"] for img in merged_metadata["images"].get("images", [])]

    for item in qa_items:
        conversations.append({
            "user": item["question"],
            "assistant": item.get("answer_hint"),
            "instruction": None, "input": None, "output": None,
            "context": merged_metadata["images"].get("caption", {}).get("long_description")
                or merged_metadata["images"].get("caption", {}).get("dataset_caption"),
            "reference": {"document_source_public_id": document_source_public_id},
            "evidence": ["MB-14 QA generation (reused, never regenerated)"],
            "image_reference": image_ids,
            "bounding_boxes": [
                o["bounding_box"] for o in merged_metadata["images"].get("objects", []) if o.get("bounding_box")
            ],
            "knowledge_graph_reference": {"node_count": knowledge_graph["node_count"], "edge_count": knowledge_graph["edge_count"]},
            "verified": False,
        })

    ocr_text = merged_metadata["text"].get("ocr_text", "")
    if ocr_text.strip():
        conversations.append({
            "user": "What does this document say?",
            "assistant": ocr_text[:OCR_ANSWER_MAX_CHARS],
            "instruction": None, "input": None, "output": None,
            "context": None,
            "reference": {"document_source_public_id": document_source_public_id},
            "evidence": ["real OCR text via Document Workspace"],
            "image_reference": [], "bounding_boxes": [],
            "knowledge_graph_reference": {"node_count": knowledge_graph["node_count"], "edge_count": knowledge_graph["edge_count"]},
            "verified": False,
        })

    return {
        "conversations": conversations, "conversation_count": len(conversations),
        "disclosure": "every turn is reused from an already-computed upstream field -- no language-generation model exists in this codebase",
    }
