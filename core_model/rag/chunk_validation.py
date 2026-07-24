"""Deterministic chunk-quality assessment.

This module only classifies; rejected or quarantined chunks must never
enter an active index — the caller (ingestion service) enforces that
exclusion.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

_PATH_PATTERN = re.compile(r"(?:^|[\s\"])(?:/home/|/etc/|/var/|/usr/|[A-Za-z]:\\)\S*")

_BLOCKING_REASONS = frozenset(
    {"empty_content", "invalid_unicode", "source_not_approved", "licence_blocked"}
)
_QUARANTINE_REASONS = frozenset({"duplicate_chunk", "metadata_leak"})


@dataclass(frozen=True)
class ChunkQualityThresholds:
    minimum_characters: int = 40
    maximum_tokens: int = 500
    ocr_noise_max_ratio: float = 0.15
    near_duplicate_similarity: float = 0.92


def ocr_noise_ratio(text: str) -> float:
    if not text:
        return 0.0
    noisy = sum(
        1 for char in text if not char.isprintable() and char not in {"\n", "\t", " "}
    )
    return noisy / len(text)


def is_valid_unicode(text: str) -> bool:
    try:
        text.encode("utf-8").decode("utf-8")
        return True
    except UnicodeError:
        return False


def detect_metadata_leak(text: str) -> bool:
    """Bounded check for accidental absolute-path leakage into chunk text —
    never a full data-loss-prevention scanner."""

    return bool(_PATH_PATTERN.search(text))


def assess_chunk_quality(
    *,
    text: str,
    language: str,
    supported_languages: tuple[str, ...],
    thresholds: ChunkQualityThresholds,
    source_approved: bool,
    licence_blocked: bool,
    is_duplicate: bool,
    estimated_token_count: int,
) -> dict[str, Any]:
    reasons: list[str] = []

    if not text.strip():
        reasons.append("empty_content")
    elif len(text) < thresholds.minimum_characters:
        reasons.append("too_short")
    if estimated_token_count > thresholds.maximum_tokens:
        reasons.append("too_long")
    if not is_valid_unicode(text):
        reasons.append("invalid_unicode")
    if ocr_noise_ratio(text) > thresholds.ocr_noise_max_ratio:
        reasons.append("ocr_noise_high")
    if language not in supported_languages and language != "unknown":
        reasons.append("unsupported_language")
    if detect_metadata_leak(text):
        reasons.append("metadata_leak")
    if is_duplicate:
        reasons.append("duplicate_chunk")
    if not source_approved:
        reasons.append("source_not_approved")
    if licence_blocked:
        reasons.append("licence_blocked")

    reason_set = set(reasons)
    if reason_set & _BLOCKING_REASONS:
        status = "rejected"
    elif reason_set & _QUARANTINE_REASONS:
        status = "quarantined"
    elif reasons:
        status = "accepted_with_warning"
    else:
        status = "accepted"

    return {"quality_status": status, "issues": reasons}


def near_duplicate_ratio(text_a: str, text_b: str) -> float:
    return SequenceMatcher(None, text_a, text_b, autojunk=False).ratio()


def detect_duplicate_and_near_duplicate(
    chunks: list[dict[str, Any]], *, near_duplicate_threshold: float
) -> dict[str, Any]:
    """Returns {"exact_duplicate_indices": set[int], "near_duplicate_pairs":
    [(i, j, ratio), ...]} — O(n^2), bounded by BRUD_RAG_MAX_CHUNKS_PER_SOURCE."""

    seen_checksums: dict[str, int] = {}
    exact_duplicate_indices: set[int] = set()
    for index, chunk in enumerate(chunks):
        checksum = chunk["content_checksum_sha256"]
        if checksum in seen_checksums:
            exact_duplicate_indices.add(index)
        else:
            seen_checksums[checksum] = index

    near_duplicate_pairs: list[tuple[int, int, float]] = []
    for i in range(len(chunks)):
        if i in exact_duplicate_indices:
            continue
        for j in range(i + 1, len(chunks)):
            if j in exact_duplicate_indices:
                continue
            ratio = near_duplicate_ratio(
                chunks[i]["normalized_text"], chunks[j]["normalized_text"]
            )
            if ratio >= near_duplicate_threshold:
                near_duplicate_pairs.append((i, j, ratio))

    return {
        "exact_duplicate_indices": exact_duplicate_indices,
        "near_duplicate_pairs": near_duplicate_pairs,
    }
