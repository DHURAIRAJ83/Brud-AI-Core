"""Brud Response Formatter -- the last pipeline step in MB-04's own
Response Flow diagram (Raw Response -> Brud Response Formatter ->
Final Response). Wraps the backend's raw generated text with the
Response Plan's own disclaimers/confidence/type and real generation
statistics. This is formatting, not chat: there is no conversation
state, no turn history, no session -- exactly what "Do NOT implement
chat" requires.
"""

from __future__ import annotations

from typing import Any


def format_response(
    *, raw_text: str, response_plan: dict[str, Any], generation_stats: dict[str, Any],
) -> dict[str, Any]:
    return {
        "text": raw_text.strip(),
        "disclaimers": response_plan.get("disclaimers", []),
        "confidence_band": response_plan.get("confidence_band"),
        "suggested_response_type": response_plan.get("suggested_response_type"),
        "intent": response_plan.get("intent"),
        "generation_stats": generation_stats,
    }
