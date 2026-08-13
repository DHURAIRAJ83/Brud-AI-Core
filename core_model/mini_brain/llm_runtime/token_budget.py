"""MB-28: Token Budget -- pure. A crude `len(text)//4` character-based
estimator (no new tokenizer dependency, disclosed as approximate) plus
the arithmetic that splits a model's context window into input/output/
system-reserve budgets.
"""

from __future__ import annotations

from typing import Any

_CHARS_PER_TOKEN_ESTIMATE = 4
_SYSTEM_RESERVE_TOKENS = 256


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN_ESTIMATE)


def compute_budget(*, context_length: int, max_tokens: int) -> dict[str, Any]:
    context_length = max(1, int(context_length))
    max_tokens = max(1, int(max_tokens))
    system_reserve = min(_SYSTEM_RESERVE_TOKENS, context_length // 4)
    output_budget = min(max_tokens, max(1, context_length - system_reserve))
    input_budget = max(1, context_length - output_budget - system_reserve)
    return {
        "context_length": context_length,
        "system_reserve_tokens": system_reserve,
        "input_budget_tokens": input_budget,
        "output_budget_tokens": output_budget,
    }


def fits_within_budget(*, text: str, budget_tokens: int) -> bool:
    return estimate_tokens(text) <= budget_tokens
