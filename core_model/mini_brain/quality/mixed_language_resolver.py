"""MB-04B: Mixed Language Resolver -- detects Tamil / English /
Tanglish / Mixed in a RESPONSE and checks it against MB-04A's own
expected output language.

Deliberately reuses MB-04A's already-built, already-tested
`language_detector` (audited, not modified, not duplicated) --
detecting the language of a piece of text is exactly the same
deterministic problem whether the text is a question or a response.
The new piece MB-04B adds here is comparing the result against what
was expected.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.prompting.language_detector import detect_language, resolve_output_language


def resolve_response_language(text: str, *, expected_output_language: str) -> dict[str, Any]:
    analysis = detect_language(text or "")
    resolved = resolve_output_language(analysis)
    return {
        **analysis,
        "resolved_output_language": resolved,
        "expected_output_language": expected_output_language,
        "matches_expectation": resolved == expected_output_language,
    }
