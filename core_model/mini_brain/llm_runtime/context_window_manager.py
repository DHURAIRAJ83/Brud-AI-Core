"""MB-28: Context Window Manager -- pure. Given the full message
history for a session plus an input-token budget (from
`token_budget.compute_budget()`), decides which turns to keep. Drops
the oldest non-system turns first, always keeping the current
question and the most recent prior reply so a truncated conversation
still reads coherently.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.llm_runtime.token_budget import estimate_tokens


def select_context_messages(
    *, messages: list[dict[str, Any]], input_budget_tokens: int
) -> dict[str, Any]:
    if not messages:
        return {"messages": [], "truncated": False, "dropped_count": 0}

    system_messages = [message for message in messages if message.get("role") == "system"]
    other_messages = [message for message in messages if message.get("role") != "system"]

    kept: list[dict[str, Any]] = list(system_messages)
    used_tokens = sum(estimate_tokens(message.get("content", "")) for message in system_messages)

    reversed_kept: list[dict[str, Any]] = []
    dropped_count = 0
    for message in reversed(other_messages):
        cost = estimate_tokens(message.get("content", ""))
        if used_tokens + cost > input_budget_tokens and reversed_kept:
            dropped_count += 1
            continue
        reversed_kept.append(message)
        used_tokens += cost

    kept.extend(reversed(reversed_kept))
    return {
        "messages": kept,
        "truncated": dropped_count > 0,
        "dropped_count": dropped_count,
    }
