"""Deterministic chunk-type classification suggestions (Phase 5, Step 10).

Every suggestion is exactly that -- a suggestion, never auto-applied.
AI-based classification is explicitly out of scope; these are plain
heuristics over the literal text, each carrying its own reason and a
fixed confidence so nothing is ever presented as more certain than a
simple pattern match actually warrants.
"""

from __future__ import annotations

import re
from typing import TypedDict

_EXAMPLE_PREFIXES = ("எடுத்துக்காட்டு", "example:", "e.g.", "eg:")
_NUMBERED_LIST_ITEM = re.compile(r"^\s*(\d+[.)]|[-*•])\s+")
_DICTIONARY_PAIR = re.compile(r"^\s*([^\s:=-]{1,40})\s*[:=-]\s*(\S.{0,120})$")


class ClassificationSuggestion(TypedDict):
    suggested_type: str
    reason: str
    confidence: float


def suggest_chunk_type(
    text: str, *, next_text: str | None = None
) -> list[ClassificationSuggestion]:
    stripped = text.strip()
    suggestions: list[ClassificationSuggestion] = []
    if not stripped:
        return suggestions

    lines = [line for line in stripped.splitlines() if line.strip()]
    is_short_standalone = len(lines) == 1 and len(stripped) <= 80
    if is_short_standalone and next_text and len(next_text.strip()) > len(stripped):
        suggestions.append(
            {
                "suggested_type": "heading",
                "reason": "a short standalone line immediately followed by longer text",
                "confidence": 0.55,
            }
        )

    lowered = stripped.lower()
    if stripped.startswith(_EXAMPLE_PREFIXES) or lowered.startswith(("example:", "e.g.", "eg:")):
        suggestions.append(
            {
                "suggested_type": "example",
                "reason": "text begins with an explicit example marker",
                "confidence": 0.8,
            }
        )

    numbered_lines = sum(1 for line in lines if _NUMBERED_LIST_ITEM.match(line))
    if lines and numbered_lines >= max(2, len(lines) // 2):
        suggestions.append(
            {
                "suggested_type": "list",
                "reason": f"{numbered_lines} of {len(lines)} line(s) start with a list marker",
                "confidence": 0.65,
            }
        )

    dictionary_like = sum(1 for line in lines if _DICTIONARY_PAIR.match(line))
    if lines and dictionary_like >= max(2, len(lines) // 2):
        suggestions.append(
            {
                "suggested_type": "dictionary_entry",
                "reason": (
                    f"{dictionary_like} of {len(lines)} line(s) look like 'term - meaning' pairs"
                ),
                "confidence": 0.6,
            }
        )

    if is_short_standalone and not suggestions:
        suggestions.append(
            {
                "suggested_type": "caption",
                "reason": "a short standalone line with no other matching pattern",
                "confidence": 0.3,
            }
        )

    return suggestions
