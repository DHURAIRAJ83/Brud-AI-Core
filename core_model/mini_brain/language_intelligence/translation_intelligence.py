"""MB-13: Translation Intelligence -- pure. Audited finding: no
Tamil<->English translation engine exists anywhere in this codebase.
This module is therefore a validator of ALREADY-CLAIMED translation
pairs an admin supplies, never a translator itself -- it checks
structural completeness (relative length ratio) and shared-numeral
terminology consistency only, never a semantic accuracy judgment, and
never invents a translation for a monolingual dataset (the common
case this phase actually runs against).
"""

from __future__ import annotations

import re
from typing import Any

MAX_ISSUES_STORED = 200
_MIN_LENGTH_RATIO = 0.3
_MAX_LENGTH_RATIO = 3.0
_NUMBER_PATTERN = re.compile(r"\d+")


def analyze_translation(*, pairs: list[dict[str, str]]) -> dict[str, Any]:
    if not pairs:
        return {
            "pairs_analyzed": 0, "completeness_issues": [], "terminology_consistency_issues": [],
            "average_confidence": None, "translation_quality_score": None,
            "disclosure": (
                "no Tamil<->English pairs were supplied for this dataset -- MB-13 never generates "
                "or invents a translation; this check only validates pairs that already exist"
            ),
        }

    completeness_issues: list[dict[str, Any]] = []
    terminology_issues: list[dict[str, Any]] = []
    confidences: list[float] = []

    for i, pair in enumerate(pairs):
        tamil_text = pair.get("tamil_text") or ""
        english_text = pair.get("english_text") or ""
        tamil_words = len(tamil_text.split())
        english_words = len(english_text.split())
        length_ratio = (english_words / tamil_words) if tamil_words else 0.0
        complete = bool(tamil_words and english_words and _MIN_LENGTH_RATIO <= length_ratio <= _MAX_LENGTH_RATIO)
        if not complete:
            completeness_issues.append({
                "pair_index": i, "tamil_word_count": tamil_words, "english_word_count": english_words,
            })

        tamil_numbers = set(_NUMBER_PATTERN.findall(tamil_text))
        english_numbers = set(_NUMBER_PATTERN.findall(english_text))
        numbers_match = tamil_numbers == english_numbers
        if not numbers_match:
            terminology_issues.append({
                "pair_index": i, "tamil_numbers": sorted(tamil_numbers), "english_numbers": sorted(english_numbers),
            })

        confidences.append(1.0 if complete and numbers_match else 0.5 if complete or numbers_match else 0.0)

    average_confidence = round(sum(confidences) / len(confidences), 3)
    return {
        "pairs_analyzed": len(pairs),
        "completeness_issues": completeness_issues[:MAX_ISSUES_STORED],
        "terminology_consistency_issues": terminology_issues[:MAX_ISSUES_STORED],
        "average_confidence": average_confidence,
        "translation_quality_score": round(average_confidence * 100, 1),
        "disclosure": (
            "structural completeness (relative length ratio) and shared-numeral consistency only "
            "-- never a semantic translation-accuracy judgment, since no real Tamil<->English "
            "translation engine exists in this codebase"
        ),
    }
