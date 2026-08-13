"""MB-14: Vision Understanding -- pure. Audited finding: no vision
model, object-detection model, or scene-classification model exists
anywhere in this codebase (confirmed by three separate existing
files' own docstrings -- see the completion report's Finding 1). This
module therefore never invents a detection: every extracted image is
honestly reported as containing one "Unknown Object" placeholder with
confidence 0.0, pending Stage 7 Admin Annotation. Never hides this
uncertainty behind a plausible-looking result.
"""

from __future__ import annotations

from typing import Any


def detect_objects(*, image_public_ids: list[str]) -> dict[str, Any]:
    placeholders = [
        {
            "image_public_id": image_public_id, "label": "Unknown Object", "confidence": 0.0,
            "admin_review_required": True,
        }
        for image_public_id in image_public_ids
    ]
    return {
        "vision_model_available": False,
        "detected_objects": placeholders,
        "object_count": 0,
        "images_pending_review": len(placeholders),
        "disclosure": (
            "no vision model exists anywhere in this codebase (confirmed by audit) -- every "
            "extracted image is honestly reported as containing an Unknown Object with confidence "
            "0.0, pending Stage 7 Admin Annotation, rather than a fabricated detection"
        ),
    }
