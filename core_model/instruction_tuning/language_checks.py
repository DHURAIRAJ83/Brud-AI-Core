"""Deterministic script-based response-language compliance checks.

Reuses the same script regexes Phase 11 already established (never
redefines them), and always keeps Tanglish as its own category — Tanglish is
Latin-script Tamil-in-transliteration and must not be folded into "English"
just because it shares a script.
"""

from __future__ import annotations

from core_model.training.dataset_profile import LATIN_PATTERN, TAMIL_PATTERN


def script_ratios(text: str) -> dict[str, float]:
    length = len(text) or 1
    tamil = len(TAMIL_PATTERN.findall(text))
    latin = len(LATIN_PATTERN.findall(text))
    return {
        "tamil_script_ratio": tamil / length,
        "latin_script_ratio": latin / length,
        "mixed_script_ratio": (1.0 if tamil and latin else 0.0),
    }


def requested_language_respected(
    text: str, expected_language: str, *, min_script_ratio: float = 0.2
) -> dict:
    """Deterministic, script-based — never an external language-detection model.

    ``expected_language`` in {ta, en, tgl, mixed}. Tanglish (tgl) expects
    Latin-script output (it is transliterated Tamil, not English) and is
    evaluated against the same latin_script_ratio as English would be, but
    reported under its own category rather than merged with English.
    """

    ratios = script_ratios(text)
    if expected_language == "ta":
        respected = ratios["tamil_script_ratio"] >= min_script_ratio
    elif expected_language in {"en", "tgl"}:
        respected = ratios["latin_script_ratio"] >= min_script_ratio
    elif expected_language == "mixed":
        respected = ratios["tamil_script_ratio"] > 0 or ratios["latin_script_ratio"] > 0
    else:
        respected = True
    return {
        "status": "pass" if respected else "warning",
        "expected_language": expected_language,
        **ratios,
    }
