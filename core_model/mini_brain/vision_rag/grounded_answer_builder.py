"""MB-17: Grounded Answer builder -- pure. Reuses `core_model.rag.
answer_policy.should_return_no_answer()` directly for the accept/
insufficient-evidence decision, and `insufficient_evidence_message()`
for the exact bilingual (Tamil/English) message the production RAG
system already uses. When evidence is sufficient, the answer is built
by concatenating real evidence snippets with citation markers -- never
a generative model, since none exists in this codebase for this
purpose. Every citation marker references a real, already-persisted
evidence row's own public_id.
"""

from __future__ import annotations

from typing import Any

from core_model.rag.answer_policy import NoAnswerThresholds, insufficient_evidence_message, should_return_no_answer

MAX_CITED_EVIDENCE = 5
THRESHOLDS = NoAnswerThresholds()


def build_grounded_answer(*, evidence: list[dict[str, Any]], language_category: str) -> dict[str, Any]:
    top_score = evidence[0]["relevance_score"] if evidence else None
    no_answer, reason = should_return_no_answer(
        context_fits=True, selected_chunk_count=len(evidence), top_combined_score=top_score,
        only_quarantined_or_blocked=False, thresholds=THRESHOLDS,
    )

    if no_answer:
        return {
            "answer": insufficient_evidence_message(language_category), "confidence": 0.0,
            "cited_evidence_public_ids": [], "status": "insufficient_evidence", "reason": reason,
        }

    # Citation markers use the "[S<n>]" convention -- the same shape
    # `core_model.rag.grounding_checks` already parses (its own
    # regex is `\[?S\d+\]?`) -- so the Hallucination Check stage can
    # reuse those functions verbatim instead of a second parser.
    cited = evidence[:MAX_CITED_EVIDENCE]
    sentences = []
    for index, item in enumerate(cited, start=1):
        snippet = item["content_snippet"] or item.get("object_label") or item["evidence_type"]
        sentences.append(f"{snippet.rstrip('.')} [S{index}].")
    answer_text = " ".join(sentences)

    return {
        "answer": answer_text, "confidence": round(top_score, 3) if top_score is not None else 0.0,
        "cited_evidence_public_ids": [item["public_id"] for item in cited],
        "status": "grounded_answer", "reason": None,
    }
