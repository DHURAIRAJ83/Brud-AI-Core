"""Extraction-method decision logic (Phase 4, Step 5).

`backend.services.document_service.process()`'s existing decision is
character-count only (`len(embedded.strip()) < ocr_min_text_length`).
This module adds Tamil-character ratio, replacement-glyph ratio, and a
crude lexical-content signal on top of that same character-count gate
-- it never replaces it, since the existing gate is still one valid,
correct signal among several. Pure function: no DB/IO, no PyMuPDF/
pytesseract imports, so it can be unit-tested without any of those
optional dependencies installed.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal, TypedDict

_TAMIL_RANGE = (0x0B80, 0x0BFF)
_REPLACEMENT_CHAR = "�"

ExtractionMethod = Literal["embedded", "ocr", "hybrid"]


class ExtractionDecision(TypedDict):
    method: ExtractionMethod
    reason: str
    signals: dict[str, float | int]


def _is_tamil(char: str) -> bool:
    return _TAMIL_RANGE[0] <= ord(char) <= _TAMIL_RANGE[1]


def _lexical_score(text: str) -> float:
    """Fraction of whitespace-delimited tokens that contain at least one
    letter -- a crude proxy for "this looks like language, not noise".
    Empty text scores 0."""

    tokens = text.split()
    if not tokens:
        return 0.0
    wordlike = sum(1 for token in tokens if any(char.isalpha() for char in token))
    return wordlike / len(tokens)


def decide_extraction_method(
    embedded_text: str,
    *,
    has_renderable_image: bool,
    min_text_length: int = 20,
    replacement_ratio_threshold: float = 0.02,
    lexical_score_threshold: float = 0.3,
) -> ExtractionDecision:
    text = unicodedata.normalize("NFC", embedded_text or "")
    stripped = text.strip()
    char_count = len(stripped)
    non_space = [char for char in text if not char.isspace()]
    tamil_count = sum(1 for char in non_space if _is_tamil(char))
    latin_count = sum(1 for char in non_space if char.isascii() and char.isalpha())
    replacement_count = text.count(_REPLACEMENT_CHAR)
    replacement_ratio = replacement_count / len(non_space) if non_space else 0.0
    tamil_ratio = tamil_count / len(non_space) if non_space else 0.0
    latin_ratio = latin_count / len(non_space) if non_space else 0.0
    lexical_score = _lexical_score(stripped)

    signals = {
        "char_count": char_count,
        "tamil_ratio": round(tamil_ratio, 4),
        "latin_ratio": round(latin_ratio, 4),
        "replacement_ratio": round(replacement_ratio, 4),
        "lexical_score": round(lexical_score, 4),
    }

    if char_count == 0:
        reason = "no_embedded_text"
        preferred: ExtractionMethod = "ocr"
    elif replacement_ratio > replacement_ratio_threshold:
        reason = "high_replacement_glyph_ratio"
        preferred = "ocr"
    elif char_count < min_text_length:
        reason = "below_minimum_text_length"
        preferred = "ocr"
    elif lexical_score < lexical_score_threshold:
        reason = "low_lexical_content"
        preferred = "hybrid"
    else:
        reason = "sufficient_embedded_text"
        preferred = "embedded"

    if preferred != "embedded" and not has_renderable_image:
        reason = f"{reason}_ocr_unavailable_no_image"
        method: ExtractionMethod = "embedded"
    else:
        method = preferred

    return {"method": method, "reason": reason, "signals": signals}


_REPEATED_PUNCTUATION = re.compile(r"([^\w\s])\1{5,}", re.UNICODE)


def has_repeated_garbage(text: str) -> bool:
    return bool(_REPEATED_PUNCTUATION.search(text))
