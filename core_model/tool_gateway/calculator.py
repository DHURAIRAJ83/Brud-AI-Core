"""Placeholder deterministic-calculator module for the Tool Gateway.
The real, full arithmetic evaluator (safe AST-based expression parsing)
is part of the Smart Routing commit group (Trusted Web + Tool Gateway)
and will replace this stub in that commit -- this file exists only so
document_sft_candidate_service.py's import succeeds before that group
lands."""

from __future__ import annotations


class CalculatorError(RuntimeError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def evaluate(expression: str):
    """Stub: the real evaluator is not registered yet. Always raises
    CalculatorError until the Smart Routing commit group replaces this
    file."""

    raise CalculatorError("not_yet_available")
