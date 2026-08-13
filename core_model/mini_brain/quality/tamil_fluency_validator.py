"""MB-04B: Tamil Fluency Validator -- deterministic, SCRIPT-LEVEL
quality checks only. This module does not and cannot judge grammar,
meaning, or genuine fluency -- that would require real language
understanding, which this phase deliberately excludes (no AI). What
it does check, precisely and defensibly:

- word repetition: identical consecutive words (plain str.split()
  comparison)
- fragment-only answers: too short to be a real answer
- mixed script / half-translated: a text expected to be Tamil that is
  actually dominated by untranslated Latin-script content
- broken Tamil script sequences: a Tamil dependent vowel sign or
  virama appearing without a preceding Tamil consonant -- this is a
  genuine Unicode/script STRUCTURAL validity rule (Tamil dependent
  vowel signs are combining marks that must attach to a base
  consonant), not a matter of linguistic opinion
- invalid punctuation: long runs of punctuation-only characters

Report only -- this module never rewrites or corrects text.
"""

from __future__ import annotations

from typing import Any

_TAMIL_CONSONANTS = frozenset(chr(c) for c in range(0x0B95, 0x0BB9 + 1))
_TAMIL_DEPENDENT_VOWEL_SIGNS = frozenset({
    "ா", "ி", "ீ", "ு", "ூ", "ெ", "ே",
    "ை", "ொ", "ோ", "ௌ", "்", "ௗ",
})

MIN_FRAGMENT_CHARS = 15
MIN_FRAGMENT_WORDS = 3
MIXED_SCRIPT_LATIN_THRESHOLD = 0.35
MAX_PUNCTUATION_RUN = 3


def _tamil_and_latin_counts(text: str) -> tuple[int, int]:
    tamil = sum(1 for ch in text if 0x0B80 <= ord(ch) <= 0x0BFF)
    latin = sum(1 for ch in text if ch.isalpha() and ch.isascii())
    return tamil, latin


def _consecutive_repeated_words(text: str) -> list[str]:
    words = text.split()
    return sorted({words[i] for i in range(1, len(words)) if words[i] == words[i - 1]})


def _find_orphan_vowel_signs(text: str) -> list[int]:
    positions = []
    for i, ch in enumerate(text):
        if ch in _TAMIL_DEPENDENT_VOWEL_SIGNS and (i == 0 or text[i - 1] not in _TAMIL_CONSONANTS):
            positions.append(i)
    return positions


def _has_excessive_punctuation_run(text: str, *, max_run: int = MAX_PUNCTUATION_RUN) -> bool:
    run = 0
    for ch in text:
        if not ch.isspace() and not ch.isalnum():
            run += 1
            if run > max_run:
                return True
        else:
            run = 0
    return False


def validate_tamil_fluency(text: str) -> dict[str, Any]:
    text = text or ""
    issues: list[str] = []
    words = text.split()

    repeated = _consecutive_repeated_words(text)
    if repeated:
        issues.append(f"word_repetition: {repeated}")

    if len(text.strip()) < MIN_FRAGMENT_CHARS or len(words) < MIN_FRAGMENT_WORDS:
        issues.append("fragment_only_answer")

    tamil_chars, latin_chars = _tamil_and_latin_counts(text)
    total = tamil_chars + latin_chars
    if total and tamil_chars > 0 and (latin_chars / total) > MIXED_SCRIPT_LATIN_THRESHOLD:
        issues.append("mixed_script_or_half_translated")

    orphan_positions = _find_orphan_vowel_signs(text)
    if orphan_positions:
        issues.append(f"broken_tamil_script_sequences: {len(orphan_positions)}")

    if _has_excessive_punctuation_run(text):
        issues.append("invalid_punctuation_pattern")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "tamil_char_count": tamil_chars,
        "latin_char_count": latin_chars,
        "word_count": len(words),
    }
