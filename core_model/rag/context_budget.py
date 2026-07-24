"""Deterministic context budgeting.

Builds bounded context within: model context length - template tokens
- query tokens - generation reserve - safety margin. Fails closed
(``fits: False``) rather than silently truncating a chunk's citation
identity or dropping the latest user question — the caller must not
proceed to generation when nothing useful fits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ContextBudget:
    maximum_model_context: int
    prompt_template_tokens: int
    query_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int

    @property
    def available_for_evidence(self) -> int:
        return (
            self.maximum_model_context
            - self.prompt_template_tokens
            - self.query_tokens
            - self.reserved_output_tokens
            - self.safety_margin_tokens
        )


def select_chunks_within_budget(
    ranked_chunks: list[dict[str, Any]], budget: ContextBudget
) -> dict[str, Any]:
    """``ranked_chunks`` must already be ordered highest-ranked first. A
    chunk is never partially included — that would split its citation
    identity — so each chunk either fits whole or is dropped."""

    available = budget.available_for_evidence
    if available <= 0:
        return {
            "selected": [],
            "dropped_count": len(ranked_chunks),
            "used_tokens": 0,
            "fits": False,
        }

    selected: list[dict[str, Any]] = []
    used = 0
    dropped = 0
    for chunk in ranked_chunks:
        tokens = chunk.get("estimated_token_count", 0)
        if used + tokens <= available:
            selected.append(chunk)
            used += tokens
        else:
            dropped += 1
    return {
        "selected": selected,
        "dropped_count": dropped,
        "used_tokens": used,
        "fits": bool(selected),
    }
