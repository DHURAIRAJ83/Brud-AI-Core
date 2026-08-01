"""Phase 20 Step 22 -- deterministic mapping between Phase 17
classification and one of the three built-in tools.

Only `ask_calculation` (Phase 17's existing `_TOOL_INTENTS` member that
this codebase can actually serve) ever selects a tool; `ask_code` (the
other `_TOOL_INTENTS` member) has no matching Phase 20 tool and always
returns `None` -- Phase 17's own classification is never modified to
accommodate this, this module simply doesn't claim a capability it
doesn't have. Never lets the request text pick an arbitrary tool name;
the return value is always one of exactly three fixed strings, or
`None`.
"""

from __future__ import annotations

import re

from core_model.tool_gateway import TOOL_NAMES

_UNIT_CONVERSION_PATTERN = re.compile(
    r"\b\d+(\.\d+)?\s*[a-zA-Z°]+\s+(to|in|into)\s+[a-zA-Z°]+\b", re.IGNORECASE
)
_ISO_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_DATE_ARITHMETIC_HINT_PATTERN = re.compile(
    r"\b(days?|weeks?|between|difference)\b", re.IGNORECASE
)


def select_tool_for_request(*, intent: str | None, text: str) -> str | None:
    if intent != "ask_calculation":
        return None

    if _UNIT_CONVERSION_PATTERN.search(text):
        tool_name = "unit_conversion"
    elif _ISO_DATE_PATTERN.search(text) and _DATE_ARITHMETIC_HINT_PATTERN.search(text):
        tool_name = "date_time_arithmetic"
    else:
        tool_name = "calculator"

    assert tool_name in TOOL_NAMES
    return tool_name


__all__ = ["select_tool_for_request"]
