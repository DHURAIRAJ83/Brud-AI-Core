"""Corpus-segment language assessment.

Reuses Phase 16's ``core_model.rag.language_routing.classify_language``
and ``core_model.instruction_tuning.language_checks.script_ratios``
unchanged for the ta/en/tgl/mixed script-ratio classification --
never a second language-detection implementation, never an external
service. Adds ``numeric``/``code`` categories and the additional
ratios this phase's corpus-quality reporting requires. Tanglish always
remains its own category, never folded into English merely because it
shares the Latin script.
"""

from __future__ import annotations

import re
from typing import Any

from core_model.instruction_tuning.language_checks import script_ratios
from core_model.rag.language_routing import DEFAULT_TANGLISH_LEXICON, classify_language

_DIGIT_PATTERN = re.compile(r"[0-9௦-௯]")
_SYMBOL_PATTERN = re.compile(r"[^\w\s஀-௿]")
_CODE_INDICATORS = re.compile(
    r"\bdef \w+\(|\bfunction \w+\(|;\s*$|^\s*(import|from|class|return)\b|[{};]", re.MULTILINE
)
_UNSUPPORTED_CHARACTER_PATTERN = re.compile(r"[�￾￿]")


def _is_mostly_numeric(text: str, digit_ratio: float) -> bool:
    return digit_ratio >= 0.6


def _is_mostly_code(text: str) -> bool:
    matches = len(_CODE_INDICATORS.findall(text))
    return matches >= 3 and len(text) < 4000


def assess_language(text: str) -> dict[str, Any]:
    length = len(text) or 1
    base = classify_language(text)
    ratios = script_ratios(text)
    digit_ratio = len(_DIGIT_PATTERN.findall(text)) / length
    symbol_ratio = len(_SYMBOL_PATTERN.findall(text)) / length
    unsupported_ratio = len(_UNSUPPORTED_CHARACTER_PATTERN.findall(text)) / length

    tokens = {token.lower().strip(".,!?;:\"'()") for token in text.split()}
    tanglish_hits = tokens & DEFAULT_TANGLISH_LEXICON
    tanglish_lexical_evidence = len(tanglish_hits) / max(1, len(tokens))
    tamil_lexical_evidence = ratios["tamil_script_ratio"]
    mixed_language_evidence = ratios["mixed_script_ratio"]

    category = base["language_category"]
    if _is_mostly_numeric(text, digit_ratio):
        category = "numeric"
    elif _is_mostly_code(text):
        category = "code"

    confidence = max(ratios["tamil_script_ratio"], ratios["latin_script_ratio"])
    if category == "mixed":
        confidence = min(0.9, confidence + 0.1)
    elif category == "unknown":
        confidence = 0.0

    return {
        "language_category": category,
        "tamil_script_ratio": ratios["tamil_script_ratio"],
        "latin_script_ratio": ratios["latin_script_ratio"],
        "digit_ratio": digit_ratio,
        "symbol_ratio": symbol_ratio,
        "tamil_lexical_evidence": tamil_lexical_evidence,
        "tanglish_lexical_evidence": tanglish_lexical_evidence,
        "mixed_language_evidence": mixed_language_evidence,
        "confidence": confidence,
        "unsupported_character_ratio": unsupported_ratio,
    }
