"""MB-16: Image Section builder -- pure. Reuses MB-14's own already-
extracted image metadata/checksum/resolution/quality and admin-
annotated objects/boxes/relationships, plus MB-15's own already-run
vision-provider predictions/corrections when a Vision Model session is
linked. Never re-extracts an image and never re-detects an object.
"""

from __future__ import annotations

from typing import Any


def build_image_section(
    *, vision_session: dict[str, Any] | None, images: list[dict[str, Any]], objects: list[dict[str, Any]],
    vision_model_session: dict[str, Any] | None, vm_predictions: list[dict[str, Any]],
    vm_corrections: list[dict[str, Any]],
) -> dict[str, Any]:
    if vision_session is None:
        return {
            "vision_session_linked": False, "image_count": 0, "images": [], "objects": [],
            "disclosure": "no MB-14 Vision Intelligence session linked -- this document has no image section",
        }

    image_metadata = [
        {
            "public_id": img["public_id"], "page_number": img["page_number"], "image_format": img["image_format"],
            "width_pixels": img["width_pixels"], "height_pixels": img["height_pixels"],
            "checksum_sha256": img["checksum_sha256"],
        }
        for img in images
    ]
    section: dict[str, Any] = {
        "vision_session_linked": True,
        "image_count": len(images),
        "images": image_metadata,
        "objects": [
            {"label": o["label"], "confidence": o["confidence"], "bounding_box": o["bounding_box"], "source": o["source"]}
            for o in objects
        ],
        "caption": vision_session.get("caption_report", {}),
        "scene": None,
        "relationships": vision_session.get("knowledge_graph_report", {}),
        "quality": vision_session.get("quality_report", {}),
        "vision_model_session_linked": vision_model_session is not None,
    }

    if vision_model_session is not None:
        section["vision_model_objects"] = [
            {"label": p["label"], "confidence": p["confidence"], "bounding_box": p["bounding_box"], "source": p["source"]}
            for p in vm_predictions
        ]
        section["scene"] = vision_model_session.get("scene_report", {})
        if vision_model_session.get("caption_report", {}).get("long_description"):
            section["caption"] = vision_model_session["caption_report"]
        section["admin_corrections"] = [
            {"action": c["action"], "wrong_label": c["wrong_label"], "correct_label": c["correct_label"]}
            for c in vm_corrections
        ]
        section["relationships"] = vision_model_session.get("knowledge_graph_report", section["relationships"])

    return section
