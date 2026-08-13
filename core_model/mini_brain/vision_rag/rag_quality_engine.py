"""MB-17: RAG Quality Engine -- pure. Combines the task spec's own
nine named metrics from already-computed retrieval/fusion/
hallucination-check output. Retrieval Recall has no ground-truth
relevance judgment to measure against (no evaluation dataset exists
for this), so it is an honest proxy -- whether any evidence was found
at all -- never a fabricated recall percentage.
"""

from __future__ import annotations

from typing import Any

EVIDENCE_COVERAGE_WEIGHT = 10.0


def score_rag_quality(
    *, text_result_count: int, ocr_result_count: int, image_result_count: int, object_result_count: int,
    graph_matched_count: int, evidence_count: int, cited_evidence_count: int, hallucination_risk: float,
) -> dict[str, Any]:
    components = {
        "retrieval_recall": 100.0 if (text_result_count or ocr_result_count) else 0.0,
        "ocr_match": 100.0 if ocr_result_count else 0.0,
        "image_match": 100.0 if image_result_count else 0.0,
        "object_match": 100.0 if object_result_count else 0.0,
        "graph_match": 100.0 if graph_matched_count else 0.0,
        "evidence_coverage": round(min(100.0, evidence_count * EVIDENCE_COVERAGE_WEIGHT), 1),
        "citation_completeness": (
            round(cited_evidence_count / evidence_count * 100, 1) if evidence_count else 0.0
        ),
        "hallucination_risk_score": round((1 - hallucination_risk) * 100, 1),
    }
    overall = round(sum(components.values()) / len(components), 1)

    return {
        "components": components, "overall_rag_quality": overall,
        "formula": "unweighted mean of 8 component scores -- no hidden weights",
        "disclosure": (
            "Retrieval Recall has no ground-truth relevance judgment to measure against -- it is "
            "whether any evidence was found at all, never a measured recall percentage"
        ),
    }
