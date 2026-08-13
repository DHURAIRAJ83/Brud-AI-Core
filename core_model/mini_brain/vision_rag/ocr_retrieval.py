"""MB-17: OCR Retrieval -- pure. Searches specifically the MB-16
records sourced from a real OCR transcription (Document Workspace's
own already-extracted text, reused by MB-16 unchanged) -- kept
separate from Text Retrieval so an admin can see exactly which
evidence came from OCR versus a caption or a QA pair.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.vision_rag.relevance_scoring import score_candidates, top_candidates

OCR_SOURCED_INSTRUCTION = "Transcribe the text visible in this document."
OCR_SOURCED_CONVERSATION_USER = "What does this document say?"
MAX_RESULTS = 5


def _ocr_text(record: dict[str, Any]) -> str | None:
    content = record["content"]
    if record["record_type"] in ("conversation", "qa") and content.get("user") == OCR_SOURCED_CONVERSATION_USER:
        return content.get("assistant")
    if record["record_type"] in ("instruction", "training") and content.get("instruction") == OCR_SOURCED_INSTRUCTION:
        return content.get("output")
    return None


def retrieve_ocr(*, normalized_query: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = []
    texts = []
    for record in records:
        text = _ocr_text(record)
        if text and text.strip():
            candidates.append(record)
            texts.append(text)

    scores = score_candidates(normalized_query=normalized_query, candidate_texts=texts)
    ranked = top_candidates(items=candidates, scores=scores, limit=MAX_RESULTS, minimum_score=0.0)

    return {
        "results": [
            {
                "record_public_id": r["public_id"], "relevance_score": r["relevance_score"],
                "ocr_snippet": _ocr_text(r),
            }
            for r in ranked
        ],
        "ocr_record_count": len(candidates), "result_count": len(ranked),
    }
