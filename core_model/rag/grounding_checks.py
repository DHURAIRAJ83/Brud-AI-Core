"""Citation validation and grounding-quality measurement.

Called ``grounding_quality``, never "factual correctness" — this module
measures whether an answer's claims are traceable to the evidence it
was given, not whether those claims are true.
"""

from __future__ import annotations

import re
from typing import Any

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_CITATION_MARKER = re.compile(r"\[?S\d+\]?")


def validate_citation(
    *,
    citation_entry: dict[str, Any] | None,
    context_chunk_ids: set[str],
    expected_checksum: str | None,
    citation_index: int,
    max_citations: int,
    already_seen: bool,
) -> dict[str, Any]:
    if citation_entry is None:
        return {"status": "not_present", "reason": "unknown_citation"}
    chunk_id = citation_entry["chunk_public_id"]
    if chunk_id not in context_chunk_ids:
        return {"status": "invalid", "reason": "citation_not_in_context"}
    if expected_checksum and citation_entry.get("content_checksum_sha256") != expected_checksum:
        return {"status": "invalid", "reason": "citation_checksum_mismatch"}
    if citation_index >= max_citations:
        return {"status": "valid_with_warning", "reason": "citation_count_exceeded"}
    if already_seen:
        return {"status": "valid_with_warning", "reason": "duplicate_citation"}
    return {"status": "valid", "reason": None}


def split_sentences(text: str) -> list[str]:
    return [sentence for sentence in _SENTENCE_SPLIT.split(text) if sentence.strip()]


def sentence_has_citation(sentence: str) -> bool:
    return bool(_CITATION_MARKER.search(sentence))


def unsupported_sentence_ratio(answer_text: str) -> float:
    """Fraction of sentences carrying no citation marker at all."""

    sentences = split_sentences(answer_text)
    if not sentences:
        return 0.0
    uncited = sum(1 for sentence in sentences if not sentence_has_citation(sentence))
    return uncited / len(sentences)


def compute_grounding_quality(
    *,
    citation_validations: list[dict[str, Any]],
    unsupported_ratio: float,
    retrieved_chunk_count: int,
    used_chunk_count: int,
    no_answer_appropriate: bool | None,
    injection_chunks_detected: int,
    injection_chunks_excluded: int,
) -> dict[str, Any]:
    valid_count = sum(
        1 for entry in citation_validations if entry["status"] in {"valid", "valid_with_warning"}
    )
    citation_validity_rate = (
        valid_count / len(citation_validations) if citation_validations else 1.0
    )
    unknown_count = sum(1 for entry in citation_validations if entry["status"] == "not_present")
    coverage = used_chunk_count / retrieved_chunk_count if retrieved_chunk_count else 0.0
    injection_resistance = (
        1.0
        if injection_chunks_detected == 0
        else injection_chunks_excluded / injection_chunks_detected
    )
    return {
        "citation_validity_rate": citation_validity_rate,
        "citation_coverage_rate": coverage,
        "unsupported_sentence_ratio": unsupported_ratio,
        "unknown_citation_count": unknown_count,
        "retrieved_context_utilization": coverage,
        "no_answer_appropriate": no_answer_appropriate,
        "injection_resistance": injection_resistance,
    }
