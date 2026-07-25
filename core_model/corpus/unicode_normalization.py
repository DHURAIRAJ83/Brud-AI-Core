"""Unicode normalization, reusing Phase 16's
``core_model.rag.text_normalization`` unchanged for NFC normalization,
newline normalization, control-character removal, and checksums --
never a second normalization implementation.

Control-character removal only strips Unicode categories ``Cc``/``Cf``
(format/control characters), which never includes Tamil vowel signs
(``Mc``), virama (``Mn``), or other combining marks (``Mn``/``Mc``) --
those are never touched by any regex here.
"""

from __future__ import annotations

import re
from typing import Any

from core_model.rag.text_normalization import content_checksum, normalize_source_text

_REPLACEMENT_CHARACTER = "�"
_MOJIBAKE_PATTERN = re.compile(r"[ÃÂ][\x80-\xbf]")
_ESCAPED_UNICODE_PATTERN = re.compile(r"\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2}")

# Tamil vowel signs (dependent vowels), virama, and combining marks --
# never removed by this or any other function in this module. Listed
# here only for the preservation check below, not for stripping.
TAMIL_VOWEL_SIGNS = "ா-்"
TAMIL_VIRAMA = "்"
TAMIL_NUMERALS = "௦-௯"


def detect_replacement_characters(text: str) -> int:
    return text.count(_REPLACEMENT_CHARACTER)


def detect_mojibake(text: str) -> int:
    return len(_MOJIBAKE_PATTERN.findall(text))


def detect_escaped_unicode(text: str) -> int:
    return len(_ESCAPED_UNICODE_PATTERN.findall(text))


def tamil_combining_marks_preserved(before: str, after: str) -> bool:
    """Verifies the Tamil vowel-sign/virama count is unchanged by
    normalization -- Tamil has no precomposed alternative for these
    combining characters, so NFC normalization must neither add nor
    remove any of them. The single most safety-critical check in this
    module."""

    before_count = len(re.findall(f"[{TAMIL_VOWEL_SIGNS}]", before))
    after_count = len(re.findall(f"[{TAMIL_VOWEL_SIGNS}]", after))
    return before_count == after_count


def assess_unicode_integrity(text: str) -> dict[str, Any]:
    replacement_count = detect_replacement_characters(text)
    mojibake_count = detect_mojibake(text)
    escaped_count = detect_escaped_unicode(text)
    if replacement_count > 0:
        status = "replacement_characters_detected"
    elif mojibake_count > 0:
        status = "mojibake_detected"
    else:
        status = "valid"
    return {
        "status": status,
        "replacement_character_count": replacement_count,
        "mojibake_count": mojibake_count,
        "escaped_unicode_count": escaped_count,
    }


def normalize_unicode(text: str) -> dict[str, Any]:
    """Wraps Phase 16's ``normalize_source_text`` and adds the
    integrity assessment Phase 19 requires on top -- no reimplementation
    of NFC/newline/control-character handling."""

    result = normalize_source_text(text, apply_ocr_correction_policy=False)
    integrity = assess_unicode_integrity(result["normalized_text"])
    combining_marks_preserved = tamil_combining_marks_preserved(text, result["normalized_text"])
    return {
        **result,
        "unicode_integrity_status": integrity["status"],
        "replacement_character_count": integrity["replacement_character_count"],
        "mojibake_count": integrity["mojibake_count"],
        "escaped_unicode_count": integrity["escaped_unicode_count"],
        "tamil_combining_marks_preserved": combining_marks_preserved,
    }


__all__ = ["content_checksum", "normalize_unicode", "assess_unicode_integrity"]
