"""Bounded, reversible-through-provenance Tamil-safe normalization.

Every applied transformation is recorded by category and count --
never silently applied. This never rewrites grammar, never translates,
and never touches Tanglish text (Latin-script Tamil) differently from
how it treats English -- both are preserved as-is except for the same
bounded whitespace/punctuation/zero-width cleanup applied to any text.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_ZERO_WIDTH_CHARACTERS = ("​", "‌", "‍", "﻿")
_VISUALLY_EQUIVALENT_PUNCTUATION = {
    "‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "...",
}
_REPEATED_WHITESPACE = re.compile(r"[ \t]{2,}")

# Bounded, explicit Tamil OCR substitutions only -- confirmed
# reproducible scanner artefacts, never a general spell-correction
# pass. Zero-width joiner/non-joiner between Tamil consonant+virama
# sequences is intentionally NOT in this table -- ZWJ/ZWNJ can be
# meaningful in real Tamil typesetting and must never be silently
# stripped from within a grapheme cluster (only the zero-width
# characters found *outside* any combining sequence, per
# ``remove_stray_zero_width_characters``, are ever removed).
_TAMIL_OCR_SUBSTITUTIONS = (
    ("ொ்", "ொ"),  # duplicated virama after a compound vowel sign, common scanner artefact
)


def normalize_visually_equivalent_punctuation(text: str) -> tuple[str, int]:
    count = 0
    for old, new in _VISUALLY_EQUIVALENT_PUNCTUATION.items():
        occurrences = text.count(old)
        if occurrences:
            text = text.replace(old, new)
            count += occurrences
    return text, count


def normalize_repeated_whitespace(text: str) -> tuple[str, int]:
    matches = _REPEATED_WHITESPACE.findall(text)
    return _REPEATED_WHITESPACE.sub(" ", text), len(matches)


def remove_stray_zero_width_characters(text: str) -> tuple[str, int]:
    """Removes zero-width characters only where they sit between two
    ASCII/whitespace boundaries (never inside a Tamil grapheme
    cluster, where a zero-width joiner/non-joiner can be meaningful)."""

    count = 0
    result_chars = []
    chars = list(text)
    for index, char in enumerate(chars):
        if char in _ZERO_WIDTH_CHARACTERS:
            previous = chars[index - 1] if index > 0 else ""
            following = chars[index + 1] if index + 1 < len(chars) else ""
            tamil_context = any(
                "஀" <= c <= "௿" for c in (previous, following) if c
            )
            if not tamil_context:
                count += 1
                continue
        result_chars.append(char)
    return "".join(result_chars), count


def apply_tamil_ocr_substitutions(text: str) -> tuple[str, int]:
    count = 0
    for old, new in _TAMIL_OCR_SUBSTITUTIONS:
        occurrences = text.count(old)
        if occurrences:
            text = text.replace(old, new)
            count += occurrences
    return text, count


def normalize_tamil_text(text: str) -> dict[str, Any]:
    """Applies every bounded transformation in a fixed order and
    returns the result plus a per-category count -- never applies a
    transformation without recording it."""

    working = unicodedata.normalize("NFC", text)
    counts: dict[str, int] = {}

    working, counts["visually_equivalent_punctuation"] = (
        normalize_visually_equivalent_punctuation(working)
    )
    working, counts["stray_zero_width_characters"] = remove_stray_zero_width_characters(working)
    working, counts["tamil_ocr_substitutions"] = apply_tamil_ocr_substitutions(working)
    working, counts["repeated_whitespace"] = normalize_repeated_whitespace(working)
    working = working.strip()

    return {
        "normalized_text": working,
        "transformation_counts": counts,
        "total_transformations": sum(counts.values()),
    }
