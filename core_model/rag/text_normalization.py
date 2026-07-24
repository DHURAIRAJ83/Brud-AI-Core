"""Deterministic source-content normalization.

Normalizes without destroying meaning: this is never translation, never
lowercasing of Tamil/mixed text, and never removal of the structural
boundaries (headings, paragraph breaks) that later chunking depends on.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any

_ALLOWED_WHITESPACE = {"\n", "\t", " "}
_REPEATED_BLANK_LINES = re.compile(r"\n{3,}")
_REPEATED_SPACES = re.compile(r"[ \t]{2,}")
_TRAILING_LINE_SPACE = re.compile(r"[ \t]+\n")

# Bounded, explicit OCR-noise substitutions only — never a general spell
# correction pass. Applied only when the caller opts in via
# ``apply_ocr_corrections=True``.
_OCR_SUBSTITUTIONS = (
    ("‘", "'"),
    ("’", "'"),
    ("“", '"'),
    ("”", '"'),
    ("ﬁ", "fi"),
    ("ﬂ", "fl"),
)


def _remove_control_characters(text: str) -> str:
    return "".join(
        char
        for char in text
        if char in _ALLOWED_WHITESPACE or unicodedata.category(char) not in {"Cc", "Cf"}
    )


def normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def apply_ocr_corrections(text: str) -> str:
    for old, new in _OCR_SUBSTITUTIONS:
        text = text.replace(old, new)
    return text


def normalize_source_text(
    text: str, *, apply_ocr_correction_policy: bool = False
) -> dict[str, Any]:
    """Returns {"normalized_text", "character_count", "checksum_sha256",
    "ocr_correction_applied"} — never mutates meaning, never translates."""

    working = unicodedata.normalize("NFC", text)
    working = normalize_newlines(working)
    working = _remove_control_characters(working)
    if apply_ocr_correction_policy:
        working = apply_ocr_corrections(working)
    working = _TRAILING_LINE_SPACE.sub("\n", working)
    working = _REPEATED_SPACES.sub(" ", working)
    working = _REPEATED_BLANK_LINES.sub("\n\n", working)
    working = working.strip()
    checksum = hashlib.sha256(working.encode("utf-8")).hexdigest()
    return {
        "normalized_text": working,
        "character_count": len(working),
        "checksum_sha256": checksum,
        "ocr_correction_applied": apply_ocr_correction_policy,
    }


def content_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
