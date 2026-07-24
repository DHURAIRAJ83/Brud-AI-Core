"""Deterministic grounded-answer status policy.

Retrieved text existing is never treated as proof the answer is
correct — this module decides only whether an answer may proceed, must
return insufficient evidence, or must be blocked, based on explicit,
checkable conditions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core_model.rag import INSUFFICIENT_EVIDENCE_MESSAGE_EN, INSUFFICIENT_EVIDENCE_MESSAGE_TA


@dataclass(frozen=True)
class NoAnswerThresholds:
    no_answer_score_threshold: float = 0.2
    minimum_citation_validity_rate: float = 0.5


def insufficient_evidence_message(language_category: str) -> str:
    if language_category == "ta":
        return INSUFFICIENT_EVIDENCE_MESSAGE_TA
    return INSUFFICIENT_EVIDENCE_MESSAGE_EN


def should_return_no_answer(
    *,
    context_fits: bool,
    selected_chunk_count: int,
    top_combined_score: float | None,
    only_quarantined_or_blocked: bool,
    thresholds: NoAnswerThresholds,
) -> tuple[bool, str | None]:
    if not context_fits or selected_chunk_count == 0:
        return True, "context_empty"
    if only_quarantined_or_blocked:
        return True, "only_quarantined_chunks"
    if top_combined_score is None or top_combined_score < thresholds.no_answer_score_threshold:
        return True, "retrieval_score_below_threshold"
    return False, None


def decide_answer_status(
    *,
    retrieval_failed: bool,
    generation_failed: bool,
    no_answer: bool,
    no_answer_reason: str | None,
    blocked_evidence_only: bool,
    grounding_quality: dict[str, Any] | None,
    thresholds: NoAnswerThresholds,
) -> dict[str, Any]:
    if retrieval_failed:
        return {"status": "retrieval_failed", "reason": "retrieval_failed"}
    if blocked_evidence_only:
        return {"status": "blocked_evidence", "reason": "only_quarantined_chunks"}
    if no_answer:
        return {"status": "insufficient_evidence", "reason": no_answer_reason}
    if generation_failed:
        return {"status": "generation_failed", "reason": "generation_failed"}
    if (
        grounding_quality is not None
        and grounding_quality["citation_validity_rate"] < thresholds.minimum_citation_validity_rate
    ):
        return {"status": "insufficient_evidence", "reason": "citation_validation_failed"}
    return {"status": "grounded_answer", "reason": None}
