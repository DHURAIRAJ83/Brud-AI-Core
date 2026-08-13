"""MB-04A: knowledge compression -- fits Knowledge Core text into a
tight prompt budget without ever exceeding the runtime's context
window. Pure text processing: dedupe, collapse repeated words,
truncate on a whole-item/whole-sentence boundary wherever possible.
No summarization model, no embeddings.
"""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
_REPEATED_WORD_RE = re.compile(r"\b(\w+)( \1\b)+", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _collapse_repeated_words(text: str) -> str:
    return _REPEATED_WORD_RE.sub(r"\1", text)


def _normalize_whitespace(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def dedupe_texts(texts: list[str]) -> list[str]:
    """Removes exact and near-duplicate (case/whitespace-insensitive)
    entries, preserving first-seen order."""

    seen: set[str] = set()
    out: list[str] = []
    for text in texts:
        key = _normalize_whitespace(text).lower()
        if key and key not in seen:
            seen.add(key)
            out.append(text)
    return out


def _truncate_to_budget(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    sentences = _SENTENCE_SPLIT_RE.split(text)
    kept: list[str] = []
    used = 0
    for sentence in sentences:
        candidate_len = used + len(sentence) + (1 if kept else 0)
        if candidate_len > max_chars:
            break
        kept.append(sentence)
        used = candidate_len
    if kept:
        return " ".join(kept)
    # A single sentence longer than the whole budget -- hard character
    # truncate as a last resort, never silently drop everything.
    return text[: max(0, max_chars - 1)].rstrip() + "…"


def compress_knowledge(texts: list[str], *, max_chars: int) -> list[str]:
    """Dedupes, collapses repeated words within each item, then fits
    the whole list into `max_chars` total -- dropping lowest-priority
    (last) items entirely before truncating a kept item's text, so the
    highest-priority knowledge always survives intact if it fits."""

    cleaned = [
        _collapse_repeated_words(_normalize_whitespace(t))
        for t in texts if t and t.strip()
    ]
    cleaned = dedupe_texts(cleaned)

    kept: list[str] = []
    remaining = max_chars
    for text in cleaned:
        if remaining <= 0:
            break
        if len(text) <= remaining:
            kept.append(text)
            remaining -= len(text)
        else:
            truncated = _truncate_to_budget(text, remaining)
            if truncated:
                kept.append(truncated)
            remaining = 0
    return kept


def compressed_char_budget(texts: list[str]) -> int:
    """How many characters the raw (uncompressed) texts would need --
    for before/after size reporting in the benchmark."""

    return sum(len(t) for t in texts)
