"""Deterministic source-content chunking.

Never merges content across sources, never mixes dataset train/test
splits (a dataset-backed source is chunked strictly from one already-
resolved source-version's text), never inserts private metadata into
chunk text. Token counts are bounded estimates (~4 characters per
token), never a claim of exact tokenizer output — a real tokenizer is
only invoked later, at embedding/generation time.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

_MARKDOWN_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
_TABLE_ROW_PATTERN = re.compile(r"^\s*\|.*\|\s*$")


def estimate_token_count(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def _is_table_block(text: str) -> bool:
    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) < 2:
        return False
    table_lines = sum(1 for line in lines if _TABLE_ROW_PATTERN.match(line))
    return table_lines / len(lines) >= 0.6


@dataclass(frozen=True)
class ChunkingConfig:
    strategy: str = "heading_aware"
    target_tokens: int = 350
    maximum_tokens: int = 500
    minimum_characters: int = 40
    overlap_tokens: int = 50
    sentence_window_sentences: int = 3


def _split_paragraphs(text: str) -> list[str]:
    return [part for part in re.split(r"\n\s*\n", text) if part.strip()]


def _split_headings(text: str) -> list[tuple[list[str], str]]:
    """Returns [(heading_path, section_text), ...] splitting at markdown-style
    '#' headings or short ALL-CAPS lines used as headings."""

    lines = text.split("\n")
    sections: list[tuple[list[str], str]] = []
    heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []

    def flush() -> None:
        joined = "\n".join(current_lines).strip()
        if joined:
            sections.append(([h for _, h in heading_stack], joined))

    for line in lines:
        stripped_line = line.strip()
        md_match = _MARKDOWN_HEADING_PATTERN.match(stripped_line)
        is_caps_heading = (
            0 < len(stripped_line) <= 60
            and stripped_line == stripped_line.upper()
            and any(char.isalpha() for char in stripped_line)
            and not stripped_line.endswith((".", ",", ";"))
        )
        if md_match:
            flush()
            current_lines = []
            level = len(md_match.group(1))
            heading_stack = [h for h in heading_stack if h[0] < level]
            heading_stack.append((level, md_match.group(2).strip()))
        elif is_caps_heading:
            flush()
            current_lines = []
            heading_stack = [h for h in heading_stack if h[0] < 1]
            heading_stack.append((1, stripped_line))
        else:
            current_lines.append(line)
    flush()
    return sections or [([], text)]


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?।])\s+", text)
    return [part for part in parts if part.strip()]


def _bounded_token_windows(text: str, config: ChunkingConfig) -> list[str]:
    words = text.split()
    if not words:
        return []
    target_words = max(1, config.target_tokens)
    overlap_words = max(0, min(config.overlap_tokens, target_words - 1))
    windows = []
    start = 0
    while start < len(words):
        end = min(len(words), start + target_words)
        windows.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap_words if end - overlap_words > start else end
    return windows


def chunk_text(
    text: str, *, config: ChunkingConfig, language: str = "unknown"
) -> list[dict[str, Any]]:
    """Deterministic chunking: same input + config always yields the same
    ordered chunks with the same checksums."""

    if config.strategy == "paragraph":
        raw_sections: list[tuple[list[str], str]] = [
            ([], part) for part in _split_paragraphs(text)
        ]
    elif config.strategy == "heading_aware":
        raw_sections = _split_headings(text)
    elif config.strategy == "sentence_window":
        sentences = _split_sentences(text)
        window = config.sentence_window_sentences
        raw_sections = [
            ([], " ".join(sentences[i : i + window]))
            for i in range(0, len(sentences), window)
        ]
    elif config.strategy == "fixed_token_window":
        raw_sections = [([], part) for part in _bounded_token_windows(text, config)]
    elif config.strategy == "record_based":
        raw_sections = [([], line) for line in text.split("\n") if line.strip()]
    else:
        raise ValueError(f"unknown chunking strategy: {config.strategy}")

    # Bounded token fallback: an over-long section is further split via
    # fixed_token_window, preserving its heading path — unless it is a
    # table block, which is kept intact and flagged too_long downstream
    # by chunk_validation rather than split mid-table.
    expanded: list[tuple[list[str], str]] = []
    for heading_path, section_text in raw_sections:
        if estimate_token_count(section_text) > config.maximum_tokens and not _is_table_block(
            section_text
        ):
            for sub in _bounded_token_windows(section_text, config):
                expanded.append((heading_path, sub))
        else:
            expanded.append((heading_path, section_text))

    chunks: list[dict[str, Any]] = []
    char_cursor = 0
    for index, (heading_path, chunk_body) in enumerate(expanded):
        stripped = chunk_body.strip()
        location = text.find(stripped, char_cursor) if stripped else -1
        if location == -1:
            location = char_cursor
        char_start = location
        char_end = location + len(stripped)
        char_cursor = max(char_cursor, char_end)
        checksum = hashlib.sha256(stripped.encode("utf-8")).hexdigest()
        chunks.append(
            {
                "sequence_number": index,
                "heading_path": heading_path,
                "source_location": {
                    "char_start": char_start,
                    "char_end": char_end,
                    "block_index": index,
                },
                "language": language,
                "normalized_text": stripped,
                "character_count": len(stripped),
                "estimated_token_count": estimate_token_count(stripped),
                "overlap_before_tokens": config.overlap_tokens if index > 0 else 0,
                "overlap_after_tokens": (
                    config.overlap_tokens if index < len(expanded) - 1 else 0
                ),
                "content_checksum_sha256": checksum,
                "is_table_block": _is_table_block(stripped),
            }
        )
    return chunks
