"""MB-17: Text Retrieval -- pure. Searches MB-16's own already-
generated conversation/QA/instruction/training records (excluding the
ones specifically sourced from OCR transcription, which are the OCR
Retrieval layer's own job) using the shared relevance-scoring
function. Never regenerates or re-derives text -- only ranks what
MB-16 already produced.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.vision_rag.relevance_scoring import score_candidates, top_candidates

OCR_SOURCED_INSTRUCTION = "Transcribe the text visible in this document."
OCR_SOURCED_CONVERSATION_USER = "What does this document say?"
MAX_RESULTS = 10


def _format_answer_value(value: Any) -> str:
    """MB-14's own QA generator answers a "Where is X located?" question
    with the real bounding box dict, not a sentence (`answer_hint`) --
    real data, honestly present, but a raw Python repr reads as broken
    to an admin. This re-presents the same real numbers as a readable
    phrase, never inventing a new fact."""
    if isinstance(value, dict) and {"x", "y", "width", "height"} <= set(value):
        return f"at position x={value['x']:.2f}, y={value['y']:.2f} within the image"
    return str(value or "")


def _record_text(record: dict[str, Any]) -> str | None:
    content = record["content"]
    if record["record_type"] in ("conversation", "qa"):
        if content.get("user") == OCR_SOURCED_CONVERSATION_USER:
            return None
        return " ".join(filter(None, [content.get("user"), _format_answer_value(content.get("assistant"))]))
    if record["record_type"] in ("instruction", "training"):
        if content.get("instruction") == OCR_SOURCED_INSTRUCTION:
            return None
        return " ".join(filter(None, [content.get("instruction"), _format_answer_value(content.get("output"))]))
    return None


def retrieve_text(*, normalized_query: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    texts = []
    for record in records:
        text = _record_text(record)
        if text and text.strip():
            candidates.append({
                "public_id": record["public_id"], "record_type": record["record_type"], "snippet": text,
            })
            texts.append(text)

    scores = score_candidates(normalized_query=normalized_query, candidate_texts=texts)
    ranked = top_candidates(items=candidates, scores=scores, limit=MAX_RESULTS)

    return {
        "results": [
            {
                "record_public_id": r["public_id"], "record_type": r["record_type"],
                "snippet": r["snippet"][:500], "relevance_score": r["relevance_score"],
            }
            for r in ranked
        ],
        "candidate_count": len(candidates), "result_count": len(ranked),
    }
