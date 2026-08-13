"""MB-16: Dataset Draft Assembler -- pure. Assembles every supported
record "flavor" (conversation, instruction, qa, caption, vision,
grounding, reasoning, training) from the already-built conversation
and instruction lists plus the merged metadata -- no new content is
synthesized here, only repackaged into each flavor's own shape.
Reasoning records are explicitly disclosed as geometric relationship
statements (from the real knowledge graph), never a fabricated
chain-of-thought, since no reasoning model exists in this codebase.
"""

from __future__ import annotations

from typing import Any

RECORD_TYPES = (
    "conversation", "instruction", "qa", "caption", "vision", "grounding", "reasoning", "training",
)


def assemble_dataset_draft(
    *, conversations: list[dict[str, Any]], instructions: list[dict[str, Any]],
    merged_metadata: dict[str, Any],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []

    for conversation in conversations:
        records.append({"record_type": "conversation", "content": conversation})
        if "MB-14 QA generation (reused, never regenerated)" in conversation.get("evidence", []):
            records.append({"record_type": "qa", "content": conversation})

    for instruction in instructions:
        records.append({"record_type": "instruction", "content": instruction})
        records.append({"record_type": "training", "content": instruction})

    images = merged_metadata["images"]
    caption = images.get("caption", {})
    caption_text = caption.get("long_description") or caption.get("dataset_caption")
    if caption_text:
        for image in images.get("images", []):
            records.append({
                "record_type": "caption",
                "content": {"image_public_id": image["public_id"], "caption": caption_text, "verified": False},
            })

    for image in images.get("images", []):
        records.append({
            "record_type": "vision",
            "content": {
                "image_public_id": image["public_id"], "objects": images.get("objects", []),
                "scene": images.get("scene"), "caption": caption_text, "verified": False,
            },
        })

    for obj in images.get("objects", []):
        if obj.get("bounding_box"):
            records.append({
                "record_type": "grounding",
                "content": {"label": obj["label"], "bounding_box": obj["bounding_box"], "confidence": obj["confidence"], "verified": False},
            })

    knowledge_graph = merged_metadata["knowledge_graph"]
    for edge in knowledge_graph.get("edges", []):
        records.append({
            "record_type": "reasoning",
            "content": {
                "statement": f"{edge['from']} {edge['relationship']} {edge['to']}",
                "basis": "real bounding-box geometry from the knowledge graph -- not a causal or semantic claim",
                "verified": False,
            },
        })

    counts_by_type: dict[str, int] = {}
    for record in records:
        counts_by_type[record["record_type"]] = counts_by_type.get(record["record_type"], 0) + 1

    return {
        "records": records, "record_count": len(records), "counts_by_type": counts_by_type,
        "status": "needs_admin_review", "verified": False,
        "disclosure": (
            "every record is repackaged from already-computed upstream data -- reasoning records are "
            "geometric relationship statements, never a fabricated chain of thought"
        ),
    }
