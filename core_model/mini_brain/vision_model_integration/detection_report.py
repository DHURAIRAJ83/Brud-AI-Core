"""MB-15: Object Detection report -- pure. Summarizes already-recorded
prediction rows (from the real backend call, or an honest empty list
when the provider was unavailable). Never invents a detection; a
`provider_available: false` input always yields `object_count: 0`.
"""

from __future__ import annotations

from typing import Any


def summarize_detections(*, provider_available: bool, predictions: list[dict[str, Any]]) -> dict[str, Any]:
    if not provider_available:
        return {
            "provider_available": False, "object_count": 0, "average_confidence": None,
            "label_counts": {}, "bounding_box_count": 0,
            "disclosure": "no vision provider produced a real detection for this session",
        }

    label_counts: dict[str, int] = {}
    confidences: list[float] = []
    boxed = 0
    for prediction in predictions:
        label_counts[prediction["label"]] = label_counts.get(prediction["label"], 0) + 1
        if prediction.get("confidence") is not None:
            confidences.append(prediction["confidence"])
        if prediction.get("bounding_box") is not None:
            boxed += 1

    average_confidence = round(sum(confidences) / len(confidences), 3) if confidences else None
    return {
        "provider_available": True, "object_count": len(predictions),
        "average_confidence": average_confidence, "label_counts": label_counts,
        "bounding_box_count": boxed,
    }
