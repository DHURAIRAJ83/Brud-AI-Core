"""MB-13: Language Quality Engine -- pure. Combines every already-
computed stage score into the task spec's eight named components plus
an Overall Language Quality figure. Never recomputes any component
itself. The Unicode component combines the Unicode Validator's and
Tamil Character Validator's scores (both are script-validity signals);
the Translation component defaults to neutral (100.0) when no pairs
were supplied, disclosed via `translation_score_applicable`.
"""

from __future__ import annotations

from typing import Any


def score_language_quality(
    *,
    unicode_score: float,
    character_score: float,
    spell_score: float,
    grammar_confidence: float,
    naturalness_score: float,
    ocr_score: float,
    tanglish_confidence: float,
    translation_score: float | None,
    dominant_language_percent: float,
) -> dict[str, Any]:
    combined_unicode = round((unicode_score + character_score) / 2, 1)
    translation_component = translation_score if translation_score is not None else 100.0

    components = {
        "unicode": combined_unicode, "spell": spell_score, "grammar": grammar_confidence,
        "sentence": naturalness_score, "translation": translation_component, "tanglish": tanglish_confidence,
        "ocr": ocr_score, "consistency": dominant_language_percent,
    }
    overall = round(sum(components.values()) / len(components), 1)

    return {
        "components": components,
        "overall_language_quality": overall,
        "translation_score_applicable": translation_score is not None,
        "formula": (
            "unweighted mean of 8 component scores (Unicode combines script-validity signals from "
            "the Unicode Validator and Tamil Character Validator) -- no hidden weights"
        ),
    }
