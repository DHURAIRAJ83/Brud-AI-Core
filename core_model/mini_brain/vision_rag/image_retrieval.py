"""MB-17: Image Retrieval -- pure. Reuses MB-14's own real image
metadata and checksums (never re-extracted) plus MB-16's own caption/
vision records for text-scoring an image against the query -- there is
no semantic image embedding anywhere in this codebase (confirmed by
audit across MB-14/15), so images are matched by their real, already-
computed caption text, never by pixel content.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.vision_rag.relevance_scoring import score_candidates, top_candidates

MAX_RESULTS = 10


def retrieve_images(
    *, normalized_query: str, images: list[dict[str, Any]], caption_records: list[dict[str, Any]],
) -> dict[str, Any]:
    caption_by_image: dict[str, str] = {}
    for record in caption_records:
        image_public_id = record["content"].get("image_public_id")
        caption = record["content"].get("caption")
        if image_public_id and caption:
            caption_by_image[image_public_id] = caption

    candidates = []
    texts = []
    for image in images:
        caption = caption_by_image.get(image["public_id"], "")
        candidates.append({**image, "caption": caption or None})
        texts.append(caption or f"page {image['page_number']} image")

    scores = score_candidates(normalized_query=normalized_query, candidate_texts=texts)
    ranked = top_candidates(items=candidates, scores=scores, limit=MAX_RESULTS, minimum_score=0.0)

    return {
        "results": [
            {
                "image_public_id": r["public_id"], "page_number": r["page_number"],
                "checksum_sha256": r["checksum_sha256"], "width_pixels": r["width_pixels"],
                "height_pixels": r["height_pixels"], "caption": r["caption"],
                "relevance_score": r["relevance_score"],
            }
            for r in ranked
        ],
        "image_count": len(images), "result_count": len(ranked),
        "disclosure": "no semantic image embedding exists in this codebase -- images are matched by their real, already-computed caption text only",
    }
