"""MB-17: Object Retrieval -- pure. Reuses MB-15's own admin-approved
vision-provider predictions when a Vision Model session is linked,
otherwise MB-14's own admin-annotated objects -- never a new object-
detection pass. Every returned object is already admin-verified,
never an "Unknown Object" placeholder.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.vision_rag.relevance_scoring import score_candidates, top_candidates

MAX_RESULTS = 15


def retrieve_objects(
    *, normalized_query: str, vision_model_objects: list[dict[str, Any]], vision_objects: list[dict[str, Any]],
) -> dict[str, Any]:
    source = "vision_model" if vision_model_objects else "vision_intelligence"
    objects = vision_model_objects if vision_model_objects else [
        o for o in vision_objects if o["source"] != "auto_unknown"
    ]

    texts = [obj["label"] for obj in objects]
    scores = score_candidates(normalized_query=normalized_query, candidate_texts=texts)
    ranked = top_candidates(items=objects, scores=scores, limit=MAX_RESULTS, minimum_score=0.0)

    return {
        "results": [
            {
                "label": r["label"], "confidence": r["confidence"], "bounding_box": r.get("bounding_box"),
                "relevance_score": r["relevance_score"],
            }
            for r in ranked
        ],
        "object_count": len(objects), "result_count": len(ranked), "source": source,
    }
