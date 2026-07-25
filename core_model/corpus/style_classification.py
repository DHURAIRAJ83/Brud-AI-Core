"""Deterministic, rule-based style classification.

Style metadata supports balancing only -- poetry and literature are
never rejected merely for differing from conversational prose; that
judgment belongs to collection policy, not this classifier.
"""

from __future__ import annotations

from typing import Any

CLASSIFIER_VERSION = "v1"

_STYLE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("question_answer", ("q:", "a:", "question:", "answer:")),
    ("dialogue", ('"', "said ", "replied ", "asked ")),
    ("dictionary_entry", ("meaning:", "definition:", "pronunciation:")),
    ("translation_pair", ("translation:", "source:", "target:")),
    ("instructional", ("step 1", "step one", "first,", "instructions:")),
    ("administrative", ("notification", "circular", "office order", "reference no")),
    ("technical", ("algorithm", "specification", "configuration", "parameter")),
    ("poetry", ("\n\n", "verse", "stanza")),
    ("narrative", ("once upon a time", "long ago", "story")),
    ("code_mixed", ("def ", "function ", "import ", "class ")),
)


def classify_style(text: str) -> dict[str, Any]:
    lowered = text.lower()
    line_count = text.count("\n") + 1
    average_line_length = len(text) / max(1, line_count)

    for style, markers in _STYLE_RULES:
        if any(marker in lowered for marker in markers):
            return {"style": style, "confidence": 0.7, "classifier_version": CLASSIFIER_VERSION}

    if average_line_length < 40 and line_count > 3:
        return {"style": "poetry", "confidence": 0.4, "classifier_version": CLASSIFIER_VERSION}

    style = "formal" if len(text) > 500 else "conversational"
    return {"style": style, "confidence": 0.3, "classifier_version": CLASSIFIER_VERSION}
