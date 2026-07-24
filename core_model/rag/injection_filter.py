"""Bounded, context-aware prompt-injection detection for retrieved chunk
content.

A chunk containing ordinary imperative how-to prose (a recipe, an
instruction manual) must never be blocked merely for using imperative
language — only phrases that specifically attempt to redirect or
override the assistant's own instructions/policies are flagged.
"""

from __future__ import annotations

import re
from typing import Any

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "ignore_previous_instructions",
        re.compile(r"\bignore (all |the )?(previous|prior|above) instructions\b", re.IGNORECASE),
    ),
    (
        "reveal_system_prompt",
        re.compile(
            r"\b(reveal|show|print|output) (the |your )?system prompt\b", re.IGNORECASE
        ),
    ),
    ("act_as_system", re.compile(r"\bact as (the )?(system|admin|developer)\b", re.IGNORECASE)),
    (
        "execute_commands",
        re.compile(
            r"\b(execute|run) (this |the following )?(command|code|script)\b", re.IGNORECASE
        ),
    ),
    (
        "change_policies",
        re.compile(
            r"\b(disregard|override|change) (your |the )?(polic(y|ies)|rules|guidelines)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "exfiltrate_secrets",
        re.compile(
            r"\b(reveal|leak|send|exfiltrate) (the |your )?(api key|password|secret|token)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "follow_these_instructions_instead",
        re.compile(r"\bfollow (these|this|the following) instructions? instead\b", re.IGNORECASE),
    ),
    (
        "tool_call_directive",
        re.compile(r"\b(call|invoke) (the )?(tool|function|api)\b", re.IGNORECASE),
    ),
    ("encoded_payload", re.compile(r"\bbase64:[A-Za-z0-9+/=]{20,}\b")),
    (
        "new_instructions_marker",
        re.compile(r"\[?system\]?\s*:\s*you (are|must)\b", re.IGNORECASE),
    ),
)

_HIGH_RISK_CATEGORIES = frozenset(
    {
        "reveal_system_prompt",
        "exfiltrate_secrets",
        "act_as_system",
        "tool_call_directive",
        "encoded_payload",
        "new_instructions_marker",
    }
)


def detect_injection_signals(text: str) -> dict[str, Any]:
    matched = [category for category, pattern in _INJECTION_PATTERNS if pattern.search(text)]
    return {"matched_categories": matched, "matched": bool(matched)}


def classify_injection_status(matched_categories: list[str], *, policy: str) -> str:
    """``policy`` is one of "block"/"quarantine"/"warn" (the retrieval
    profile's ``injection_filter_policy``)."""

    if not matched_categories:
        return "clean"
    if any(category in _HIGH_RISK_CATEGORIES for category in matched_categories):
        return "blocked" if policy == "block" else "quarantined"
    if policy == "warn":
        return "warning"
    if policy == "quarantine":
        return "quarantined"
    return "blocked"
