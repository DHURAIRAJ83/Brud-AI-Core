"""Deterministic document segmentation into pretraining-ready units.

Never merges content across different source snapshots -- every
segmentation call operates on exactly one normalized document's text.
Empty segments are always rejected. The recommended default is
``heading_section`` with a ``paragraph`` fallback when no heading
structure is detected.
"""

from __future__ import annotations

import re
from typing import Any

_HEADING_PATTERN = re.compile(r"^(#{1,6}\s+.+|[A-Z][A-Za-z0-9 ]{2,60}:?\s*)$", re.MULTILINE)
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?।॥])\s+")


def content_checksum(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate_token_count(text: str) -> int:
    """A bounded, deterministic whitespace-based estimate -- never a
    real tokenizer call during segmentation, which would be far too
    slow for bulk corpus processing."""

    return max(1, len(text) // 4)


def estimate_sentence_count(text: str) -> int:
    return len([s for s in _SENTENCE_BOUNDARY.split(text) if s.strip()])


def split_into_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in _PARAGRAPH_SPLIT.split(text) if p.strip()]


def split_into_heading_sections(text: str) -> list[dict[str, Any]]:
    """Returns [{"heading": str | None, "text": str}, ...]. Falls back
    to a single section with no heading if none are detected."""

    matches = list(_HEADING_PATTERN.finditer(text))
    if not matches:
        return [{"heading": None, "text": text}]

    sections = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append({"heading": match.group().strip(), "text": body})
    if not sections:
        return [{"heading": None, "text": text}]
    return sections


def split_fixed_character_window(
    text: str, *, window_size: int, overlap: int = 0
) -> list[str]:
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    step = max(1, window_size - overlap)
    return [
        text[i : i + window_size]
        for i in range(0, len(text), step)
        if text[i : i + window_size].strip()
    ]


def split_record_based(records: list[dict[str, str]]) -> list[str]:
    """For dictionary entries, FAQ pairs, and parallel text -- each
    record becomes exactly one segment, never merged with its
    neighbours regardless of length."""

    return [record["text"] for record in records if record.get("text", "").strip()]


def segment_document(
    text: str,
    *,
    strategy: str,
    minimum_characters: int,
    maximum_characters: int,
    heading_hierarchy: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Returns a list of segment payloads (no persistence). Every
    segment's ``character_count`` is guaranteed to be > 0; empty
    segments are dropped, never emitted as zero-length placeholders."""

    if strategy == "heading_section":
        sections = split_into_heading_sections(text)
        raw_segments = []
        for section in sections:
            heading = [section["heading"]] if section["heading"] else []
            for paragraph in split_into_paragraphs(section["text"]) or [section["text"]]:
                raw_segments.append({"text": paragraph, "heading_hierarchy": heading})
    elif strategy == "paragraph":
        raw_segments = [
            {"text": paragraph, "heading_hierarchy": heading_hierarchy or []}
            for paragraph in split_into_paragraphs(text)
        ]
    elif strategy == "sentence_group":
        sentences = [s.strip() for s in _SENTENCE_BOUNDARY.split(text) if s.strip()]
        raw_segments = [
            {"text": sentence, "heading_hierarchy": heading_hierarchy or []}
            for sentence in sentences
        ]
    elif strategy == "fixed_character_window":
        raw_segments = [
            {"text": window, "heading_hierarchy": heading_hierarchy or []}
            for window in split_fixed_character_window(text, window_size=maximum_characters)
        ]
    else:
        raw_segments = [{"text": text, "heading_hierarchy": heading_hierarchy or []}]

    segments: list[dict[str, Any]] = []
    for sequence, raw in enumerate(raw_segments):
        body = raw["text"].strip()
        if not body:
            continue
        if len(body) > maximum_characters:
            continue
        if len(body) < minimum_characters and strategy not in {"record_based", "sentence_group"}:
            continue
        segments.append(
            {
                "sequence_number": sequence,
                "segmentation_strategy": strategy,
                "heading_hierarchy": raw["heading_hierarchy"],
                "text": body,
                "text_checksum_sha256": content_checksum(body),
                "character_count": len(body),
                "sentence_count": estimate_sentence_count(body),
                "token_estimate": estimate_token_count(body),
            }
        )
    return segments
