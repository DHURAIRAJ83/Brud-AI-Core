"""MB-13: Tamil Grammar Analyzer -- pure, SCRIPT-STRUCTURAL heuristics
only. Audited finding: no real Tamil grammatical analysis capability
(verb agreement, gender, number, case, tense) exists anywhere in this
codebase, and building one would require genuine NLP/linguistic
understanding this project deliberately excludes everywhere else (see
`tamil_fluency_validator`'s own docstring). This module never
fabricates a grammatical judgment -- it checks only terminal
punctuation presence, sentence length bounds, and the presence of a
small set of common Tamil verb-ending morphemes as a weak "verb likely
present" signal, and reports every one of the five requested checks it
cannot honestly perform.
"""

from __future__ import annotations

from typing import Any

_COMMON_VERB_SUFFIXES = (
    "கிறது", "கிறேன்", "கிறார்", "கிறாள்", "கிறான்", "கிறோம்", "கிறீர்கள்",
    "ந்தது", "ந்தேன்", "ந்தார்", "கும்", "டும்", "வேன்", "வோம்", "கின்றன", "ட்டது",
)
MAX_WORDS_PER_SENTENCE = 60
NOT_IMPLEMENTED = ("verb_agreement", "gender_agreement", "number_agreement", "case_analysis", "tense_analysis")


def analyze_grammar(*, texts: list[str]) -> dict[str, Any]:
    total = len(texts)
    missing_terminal_punctuation = 0
    verb_signal_present_count = 0
    run_on_count = 0

    for text in texts:
        stripped = (text or "").strip()
        if stripped and stripped[-1] not in ".?!":
            missing_terminal_punctuation += 1
        if any(suffix in text for suffix in _COMMON_VERB_SUFFIXES):
            verb_signal_present_count += 1
        if len(stripped.split()) > MAX_WORDS_PER_SENTENCE:
            run_on_count += 1

    total_or_one = total or 1
    grammar_confidence = round(
        max(0.0, 100.0 - (missing_terminal_punctuation + run_on_count) / total_or_one * 50.0), 1,
    )

    return {
        "records_analyzed": total,
        "missing_terminal_punctuation_count": missing_terminal_punctuation,
        "verb_signal_present_count": verb_signal_present_count,
        "run_on_sentence_count": run_on_count,
        "grammar_confidence": grammar_confidence,
        "not_implemented": list(NOT_IMPLEMENTED),
        "disclosure": (
            "this is a script-structural heuristic only (terminal punctuation, sentence length, "
            "common verb-suffix presence) -- real grammatical analysis (verb agreement, gender, "
            "number, case, tense) requires genuine NLP/linguistic understanding that does not exist "
            "anywhere in this codebase and is NOT implemented here; grammar_confidence must never be "
            "read as a claim of grammatical correctness"
        ),
    }
