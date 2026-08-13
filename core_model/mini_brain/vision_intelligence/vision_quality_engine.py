"""MB-14: Vision Quality Engine -- pure. Combines every already-
computed stage score into the task spec's seven named components plus
an Overall Vision Score. Every formula is disclosed. Object Accuracy
and Scene Accuracy have no vision model to measure against, so both
are honest proxies from the only real signal available (admin
verification), never a fabricated accuracy figure.
"""

from __future__ import annotations

from typing import Any

QA_QUESTION_SCORE_WEIGHT = 10.0
KG_EDGE_SCORE_WEIGHT = 20.0


def score_vision_quality(
    *,
    average_image_quality_score: float,
    average_ocr_match_ratio: float | None,
    caption_available: bool,
    total_object_count: int,
    admin_verified_object_count: int,
    qa_question_count: int,
    kg_edge_count: int,
) -> dict[str, Any]:
    ocr_match_score = round((average_ocr_match_ratio or 0.0) * 100, 1)
    caption_quality_score = 100.0 if caption_available else 0.0
    object_accuracy_score = (
        round(admin_verified_object_count / total_object_count * 100, 1) if total_object_count else 0.0
    )
    scene_accuracy_score = 100.0 if caption_available else 0.0
    qa_quality_score = round(min(100.0, qa_question_count * QA_QUESTION_SCORE_WEIGHT), 1)
    kg_quality_score = round(min(100.0, kg_edge_count * KG_EDGE_SCORE_WEIGHT), 1)

    components = {
        "image_quality": round(average_image_quality_score, 1), "ocr_match": ocr_match_score,
        "caption_quality": caption_quality_score, "object_accuracy": object_accuracy_score,
        "scene_accuracy": scene_accuracy_score, "qa_quality": qa_quality_score,
        "knowledge_graph_quality": kg_quality_score,
    }
    overall = round(sum(components.values()) / len(components), 1)

    return {
        "components": components,
        "overall_vision_score": overall,
        "formula": "unweighted mean of 7 component scores -- no hidden weights",
        "disclosure": (
            "Object Accuracy is the share of objects an admin has verified/corrected (no vision "
            "model exists to measure real detection accuracy against); Scene Accuracy is a proxy "
            "from caption presence only, for the same reason -- neither is a measured accuracy figure"
        ),
    }
