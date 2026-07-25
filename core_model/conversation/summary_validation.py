"""Conversation summary validation.

An invalid summary must never enter context -- this module is the
gate between a generated/extracted summary and its acceptance.
"""

from __future__ import annotations

import re
from typing import Any

from core_model.conversation.memory_safety import assess_memory_safety
from core_model.conversation.turn_validation import is_valid_unicode

_NUMBER_PATTERN = re.compile(r"\b\d[\d,.]*\b")
_ROLE_TOKEN_PATTERN = re.compile(r"<(system|user|assistant|bos|eos)>", re.IGNORECASE)
_HIDDEN_PROMPT_MARKERS = ("system instructions", "hidden prompt", "you are an ai")


def _numbers_in(text: str) -> set[str]:
    return set(_NUMBER_PATTERN.findall(text))


def validate_summary(
    *,
    summary_text: str,
    source_turns: list[dict[str, Any]],
    maximum_tokens: int,
    estimated_token_count: int,
    language_category: str,
    expected_language_category: str | None,
) -> dict[str, Any]:
    issues: list[str] = []

    source_text = "\n".join(turn["content"] for turn in source_turns)
    source_numbers = _numbers_in(source_text)
    summary_numbers = _numbers_in(summary_text)
    if summary_numbers - source_numbers:
        issues.append("unsupported_number_or_date")

    safety = assess_memory_safety(summary_text)
    if safety["status"] == "blocked":
        issues.append("secret_leakage")

    if _ROLE_TOKEN_PATTERN.search(summary_text):
        issues.append("role_token_leakage")

    lowered = summary_text.lower()
    if any(marker in lowered for marker in _HIDDEN_PROMPT_MARKERS):
        issues.append("hidden_system_prompt_leakage")

    if not source_turns:
        issues.append("no_source_turn_coverage")

    if expected_language_category and language_category != expected_language_category:
        issues.append("language_noncompliant")

    if estimated_token_count > maximum_tokens:
        issues.append("maximum_tokens_exceeded")

    if not is_valid_unicode(summary_text):
        issues.append("invalid_unicode")

    return {"valid": not issues, "issues": issues}
