"""MB-16: Dataset Quality Engine -- pure. Combines the task spec's own
nine named metrics from already-computed upstream scores (MB-13's
language quality, MB-14/MB-15's vision/OCR/object quality) plus two
new structural completeness checks (Conversation Quality, Instruction
Quality) this phase itself introduces. Every formula is disclosed;
nothing here is a fabricated accuracy figure.
"""

from __future__ import annotations

from typing import Any

KNOWLEDGE_GRAPH_EDGE_WEIGHT = 20.0


def score_dataset_quality(
    *, language_quality_score: float | None, vision_quality_score: float | None,
    ocr_match_score: float | None, object_quality_score: float | None,
    caption_quality_score: float | None, knowledge_graph_edge_count: int,
    conversation_count: int, instruction_count: int,
) -> dict[str, Any]:
    knowledge_graph_quality_score = round(min(100.0, knowledge_graph_edge_count * KNOWLEDGE_GRAPH_EDGE_WEIGHT), 1)
    conversation_quality_score = 100.0 if conversation_count > 0 else 0.0
    instruction_quality_score = 100.0 if instruction_count > 0 else 0.0

    components = {
        "language_quality": round(language_quality_score, 1) if language_quality_score is not None else 0.0,
        "vision_quality": round(vision_quality_score, 1) if vision_quality_score is not None else 0.0,
        "ocr_match": round(ocr_match_score, 1) if ocr_match_score is not None else 0.0,
        "object_quality": round(object_quality_score, 1) if object_quality_score is not None else 0.0,
        "caption_quality": round(caption_quality_score, 1) if caption_quality_score is not None else 0.0,
        "knowledge_graph_quality": knowledge_graph_quality_score,
        "conversation_quality": conversation_quality_score,
        "instruction_quality": instruction_quality_score,
    }
    overall = round(sum(components.values()) / len(components), 1)

    return {
        "components": components, "overall_dataset_quality": overall,
        "formula": "unweighted mean of 8 component scores -- no hidden weights",
        "disclosure": (
            "components with no linked upstream session (language/vision/OCR/object/caption) score 0, "
            "not a fabricated passing value -- an absent source is a missing signal, not a good one"
        ),
    }
