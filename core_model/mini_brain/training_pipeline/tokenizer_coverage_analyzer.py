"""MB-18: Tokenizer Coverage Analyzer -- pure, CPU-safe, no tokenizer
ever loaded. Computes real character-level statistics from already-
collected text: unique character coverage, a real Unicode category
histogram (via Python's own `unicodedata`, never a fabricated
distribution), and Tamil/Latin script ratios reused directly from
`core_model.instruction_tuning.language_checks.script_ratios()` --
the same function `core_model.rag.language_routing.classify_language()`
itself already relies on. Every text is scored independently and
combined by a length-weighted average, so no snippet's characters are
ever concatenated into one giant string -- bounded memory regardless
of corpus size.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from core_model.instruction_tuning.language_checks import script_ratios

_RISKY_CATEGORIES = {"Co", "Cn", "Cs"}  # private-use, unassigned, surrogate


def analyze_tokenizer_coverage(*, texts: list[str]) -> dict[str, Any]:
    if not texts:
        return {
            "unique_character_count": 0, "total_character_count": 0, "unicode_category_distribution": {},
            "tamil_ratio": 0.0, "latin_ratio": 0.0, "digit_ratio": 0.0, "punctuation_ratio": 0.0,
            "unseen_character_risk": 0.0, "script_mix": [],
            "disclosure": "no text was supplied -- coverage is honestly empty, not fabricated",
        }

    unique_chars: set[str] = set()
    category_counts: dict[str, int] = {}
    digit_count = 0
    punctuation_count = 0
    risky_count = 0
    total_chars = 0
    weighted_tamil = 0.0
    weighted_latin = 0.0

    for text in texts:
        length = len(text)
        if length == 0:
            continue
        total_chars += length
        ratios = script_ratios(text)
        weighted_tamil += ratios["tamil_script_ratio"] * length
        weighted_latin += ratios["latin_script_ratio"] * length

        for char in text:
            unique_chars.add(char)
            category = unicodedata.category(char)
            category_counts[category] = category_counts.get(category, 0) + 1
            if category.startswith("N"):
                digit_count += 1
            elif category.startswith("P"):
                punctuation_count += 1
            if category in _RISKY_CATEGORIES:
                risky_count += 1

    tamil_ratio = round(weighted_tamil / total_chars, 4) if total_chars else 0.0
    latin_ratio = round(weighted_latin / total_chars, 4) if total_chars else 0.0
    digit_ratio = round(digit_count / total_chars, 4) if total_chars else 0.0
    punctuation_ratio = round(punctuation_count / total_chars, 4) if total_chars else 0.0
    unseen_character_risk = round(risky_count / total_chars, 4) if total_chars else 0.0

    script_mix = []
    if tamil_ratio > 0.05:
        script_mix.append("tamil")
    if latin_ratio > 0.05:
        script_mix.append("latin")
    if digit_ratio > 0.02:
        script_mix.append("digits")
    if punctuation_ratio > 0.02:
        script_mix.append("punctuation")

    return {
        "unique_character_count": len(unique_chars), "total_character_count": total_chars,
        "unicode_category_distribution": category_counts,
        "tamil_ratio": tamil_ratio, "latin_ratio": latin_ratio, "digit_ratio": digit_ratio,
        "punctuation_ratio": punctuation_ratio, "unseen_character_risk": unseen_character_risk,
        "script_mix": script_mix,
        "disclosure": "no tokenizer was loaded -- this is character-level analysis only, not real subword/vocabulary coverage against any specific tokenizer",
    }
