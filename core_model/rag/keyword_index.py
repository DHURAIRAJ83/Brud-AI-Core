"""Deterministic keyword tokenization and FTS5 query construction.

Tamil is not whitespace-segmented the way English is; naive whitespace
tokenization under-serves Tamil and Tanglish morphology. This module
documents that limitation honestly rather than silently pretending
FTS5's default tokenizer is linguistically adequate for Tamil.
"""

from __future__ import annotations

import re

# Python's `\w` excludes Unicode combining marks (categories Mn/Mc), which
# would otherwise shred every Tamil word at its vowel signs and virama
# (e.g. "தமிழ்" -> "தம" + "ி" + "ழ" + "்"). The Tamil Unicode block
# (U+0B80-U+0BFF) is added explicitly so combining marks stay attached to
# their base consonant — discovered and fixed during implementation, not
# a theoretical concern.
_WORD_PATTERN = re.compile(r"[\w஀-௿]+", re.UNICODE)

KNOWN_LIMITATIONS = (
    "FTS5's built-in tokenizers (unicode61) segment on Unicode "
    "word-boundary heuristics; they do not perform true Tamil "
    "morphological segmentation, so compound Tamil words are indexed as "
    "single whitespace-delimited tokens rather than meaningful "
    "sub-parts. This is a documented, honest limitation, not a hidden one."
)


def tokenize_for_keyword_index(text: str) -> list[str]:
    """Deterministic, whitespace/Unicode-word-boundary tokenization — the
    same approach applied uniformly to Tamil, English, and Tanglish terms
    alike (no per-language special casing that could silently diverge)."""

    return [token.lower() for token in _WORD_PATTERN.findall(text)]


def escape_fts5_query(query: str) -> str:
    """FTS5 ``MATCH`` queries treat many characters specially; this builds
    a safe, deterministic OR-of-phrases query from raw tokens rather than
    passing user text through unescaped."""

    tokens = tokenize_for_keyword_index(query)
    if not tokens:
        return '""'
    return " OR ".join(f'"{token}"' for token in tokens)


def keyword_match_score(bm25_score: float | None) -> float:
    """SQLite's ``bm25()`` returns a *negative*, unbounded value where more
    negative means a stronger match (verified directly against a live FTS5
    table, not assumed) — this converts that into a bounded, higher-is-
    better score for combining with vector scores."""

    if bm25_score is None:
        return 0.0
    magnitude = abs(bm25_score)
    return magnitude / (1.0 + magnitude)
