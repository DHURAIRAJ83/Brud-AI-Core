"""MB-15: Vision Model Quality Engine -- pure. Combines every already-
computed stage output into the task spec's own seven named component
scores plus an Overall Score. Every formula is disclosed. Detection
Accuracy has no ground truth to measure against (no vision model
exists to have been benchmarked), so it is an honest proxy from the
only real signal available -- the share of predictions an admin left
approved and unchanged -- never a fabricated accuracy figure.
"""

from __future__ import annotations

from typing import Any

RELATIONSHIP_EDGE_WEIGHT = 20.0


def score_vision_model_quality(
    *, total_predictions: int, approved_unchanged_count: int, caption_available: bool,
    scene_available: bool, bounding_box_count: int, relationship_edge_count: int,
    correction_rate: float | None, average_confidence: float | None,
) -> dict[str, Any]:
    detection_accuracy = (
        round(approved_unchanged_count / total_predictions * 100, 1) if total_predictions else 0.0
    )
    caption_quality = 100.0 if caption_available else 0.0
    scene_accuracy = 100.0 if scene_available else 0.0
    bounding_box_quality = (
        round(bounding_box_count / total_predictions * 100, 1) if total_predictions else 0.0
    )
    relationship_quality = round(min(100.0, relationship_edge_count * RELATIONSHIP_EDGE_WEIGHT), 1)
    correction_rate_score = round((1 - correction_rate) * 100, 1) if correction_rate is not None else 100.0
    confidence_score = round(average_confidence * 100, 1) if average_confidence is not None else 0.0

    components = {
        "detection_accuracy": detection_accuracy, "caption_quality": caption_quality,
        "scene_accuracy": scene_accuracy, "bounding_box_quality": bounding_box_quality,
        "relationship_quality": relationship_quality, "correction_rate_score": correction_rate_score,
        "confidence": confidence_score,
    }
    overall = round(sum(components.values()) / len(components), 1)

    return {
        "components": components, "overall_vision_model_score": overall,
        "raw_correction_rate": correction_rate,
        "formula": "unweighted mean of 7 component scores -- no hidden weights",
        "disclosure": (
            "Detection Accuracy is the share of predictions an admin left approved and unchanged "
            "(no vision model exists to have been benchmarked against real ground truth); Bounding "
            "Box Quality reflects that most providers in this codebase cannot produce a real box at "
            "all -- neither is a measured accuracy figure"
        ),
    }
