"""MB-14: Bounding Box Planner -- pure. Audited finding: no
object-detection model exists anywhere in this codebase, so no box is
ever planned automatically. This module only classifies already-
admin-drawn boxes (from Stage 7 Admin Annotation) into a plan; nothing
here is auto-accepted.
"""

from __future__ import annotations

from typing import Any


def plan_bounding_boxes(*, objects: list[dict[str, Any]]) -> dict[str, Any]:
    boxes = [
        {
            "object_public_id": o["public_id"], "object_label": o["label"],
            "bounding_box": o["bounding_box"], "confidence": o["confidence"], "source": o["source"],
        }
        for o in objects if o.get("bounding_box") is not None
    ]
    unboxed = [o for o in objects if o.get("bounding_box") is None]

    return {
        "planned_boxes": boxes, "box_count": len(boxes), "auto_accepted": False,
        "unboxed_object_count": len(unboxed),
        "disclosure": (
            "no object-detection model exists anywhere in this codebase (confirmed by audit) -- "
            "bounding boxes only ever come from an admin drawing one via Stage 7 Admin Annotation; "
            "nothing here is auto-accepted"
        ),
    }
