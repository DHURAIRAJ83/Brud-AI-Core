"""Phase 20 Step 21/22 -- bounded, best-effort extraction of a
structured tool input payload from the free-text public chat message,
once `select_tool_for_request()` has already picked a tool name.

Returns `None` when extraction isn't confident -- the caller treats
that as `tool_input_invalid`/ambiguous, never guesses a value. This is
deliberately narrow regex extraction, not an NLP parser: it only needs
to cover the patterns Phase 17 itself would have classified as
`ask_calculation` in the first place.
"""

from __future__ import annotations

import re
from typing import Any

_EXPRESSION_FRAGMENT_RE = re.compile(r"[-+*/().%\d\s]{2,}")
_UNIT_CONVERSION_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*([a-zA-Z°]+)\s+(?:to|in|into)\s+([a-zA-Z°]+)", re.IGNORECASE
)
_TWO_DATES_RE = re.compile(r"(\d{4}-\d{2}-\d{2}).{0,30}?(\d{4}-\d{2}-\d{2})")
_BETWEEN_HINT_RE = re.compile(r"\b(between|difference)\b", re.IGNORECASE)
_ADD_DELTA_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2}).{0,15}?([+-]|\bplus\b|\bminus\b|\badd\b|\bsubtract\b)\s*"
    r"(\d+)\s*(day|days|week|weeks)\b",
    re.IGNORECASE,
)
_NEGATIVE_WORDS = frozenset({"-", "minus", "subtract"})


def _extract_calculator_input(text: str) -> dict[str, Any] | None:
    candidates = [
        fragment.strip()
        for fragment in _EXPRESSION_FRAGMENT_RE.findall(text)
        if any(char.isdigit() for char in fragment)
        and any(op in fragment for op in "+-*/%")
    ]
    if not candidates:
        return None
    return {"expression": max(candidates, key=len)}


def _extract_unit_conversion_input(text: str) -> dict[str, Any] | None:
    match = _UNIT_CONVERSION_RE.search(text)
    if not match:
        return None
    value_text, source_unit, target_unit = match.groups()
    return {"value": float(value_text), "source_unit": source_unit, "target_unit": target_unit}


def _extract_date_time_arithmetic_input(text: str) -> dict[str, Any] | None:
    two_dates = _TWO_DATES_RE.search(text)
    if two_dates and _BETWEEN_HINT_RE.search(text):
        return {
            "operation": "date_difference",
            "date_a": two_dates.group(1),
            "date_b": two_dates.group(2),
        }

    delta = _ADD_DELTA_RE.search(text)
    if delta:
        date_value, sign_word, amount_text, unit_word = delta.groups()
        amount = int(amount_text)
        if sign_word.lower() in _NEGATIVE_WORDS:
            amount = -amount
        if unit_word.lower().startswith("week"):
            return {"operation": "add_weeks", "date": date_value, "weeks": amount}
        return {"operation": "add_days", "date": date_value, "days": amount}

    return None


_EXTRACTORS = {
    "calculator": _extract_calculator_input,
    "unit_conversion": _extract_unit_conversion_input,
    "date_time_arithmetic": _extract_date_time_arithmetic_input,
}


def extract_tool_input(tool_name: str, text: str) -> dict[str, Any] | None:
    extractor = _EXTRACTORS.get(tool_name)
    if extractor is None:
        return None
    return extractor(text)


__all__ = ["extract_tool_input"]
