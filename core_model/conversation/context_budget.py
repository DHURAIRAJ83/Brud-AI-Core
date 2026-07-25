"""Chat orchestration context budgeting.

Fails closed if the current request and mandatory system instructions
do not fit -- the latest user message is never silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChatContextBudget:
    maximum_model_context: int
    system_tokens: int
    current_request_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int = 10
    conversation_budget_tokens: int = 300
    summary_budget_tokens: int = 150
    memory_budget_tokens: int = 200
    rag_budget_tokens: int = 400

    @property
    def mandatory_tokens(self) -> int:
        return (
            self.system_tokens + self.current_request_tokens
            + self.reserved_output_tokens + self.safety_margin_tokens
        )

    @property
    def fits_mandatory(self) -> bool:
        return self.mandatory_tokens <= self.maximum_model_context

    @property
    def available_for_optional(self) -> int:
        return max(0, self.maximum_model_context - self.mandatory_tokens)


def allocate_optional_budgets(budget: ChatContextBudget) -> dict[str, int]:
    """Scales the four optional-item budgets down proportionally if the
    model context is too small to fit them all at their configured
    sizes -- never expands past what actually fits."""

    requested = {
        "conversation": budget.conversation_budget_tokens,
        "summary": budget.summary_budget_tokens,
        "memory": budget.memory_budget_tokens,
        "rag": budget.rag_budget_tokens,
    }
    total_requested = sum(requested.values())
    available = budget.available_for_optional
    if total_requested <= available or total_requested == 0:
        return requested
    scale = available / total_requested
    return {key: int(value * scale) for key, value in requested.items()}


def select_items_within_budget(
    ranked_items: list[dict[str, Any]], *, budget_tokens: int
) -> dict[str, Any]:
    """Whole-item-only inclusion in rank order -- an item is never split."""

    selected: list[dict[str, Any]] = []
    used = 0
    dropped = 0
    for item in ranked_items:
        item_tokens = item["token_count"]
        if used + item_tokens <= budget_tokens:
            selected.append(item)
            used += item_tokens
        else:
            dropped += 1
    return {"selected": selected, "used_tokens": used, "dropped_count": dropped}
