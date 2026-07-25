"""Feedback safety scanning.

Reuses Phase 12/13's ``core_model.instruction_tuning.evaluation``
structural checks (role-token leakage, prompt/system leakage,
repetition) unchanged, and Phase 16's RAG injection-pattern detection
unchanged for unsafe-instruction/injection-style content -- never a
second implementation of any of these checks.
"""

from __future__ import annotations

from typing import Any

from core_model.instruction_tuning.evaluation import (
    no_excessive_repetition,
    no_role_token_leakage,
    no_system_prompt_leakage,
)
from core_model.rag.injection_filter import classify_injection_status, detect_injection_signals

_BLOCKING_INJECTION_CATEGORIES = frozenset(
    {"reveal_system_prompt", "exfiltrate_secrets", "act_as_system", "execute_commands"}
)


def assess_feedback_safety(
    text: str, *, system_text: str | None = None, user_text: str | None = None
) -> dict[str, Any]:
    """Scans free-text feedback content (comments, suggested corrections)
    for unsafe-instruction / injection-style patterns and structural
    leakage. Returns ``safe`` / ``flagged`` / ``blocked`` plus the
    specific matched categories -- never the raw matched span."""

    injection_signals = detect_injection_signals(text)
    matched = injection_signals["matched_categories"]
    leakage = no_system_prompt_leakage(text, system_text, user_text)
    role_leakage = no_role_token_leakage(text)

    categories: list[str] = list(matched)
    if leakage["status"] == "fail":
        categories.append("prompt_leakage")
    if role_leakage["status"] == "fail":
        categories.append("role_token_leakage")

    if any(category in _BLOCKING_INJECTION_CATEGORIES for category in matched):
        status = "blocked"
    elif categories:
        status = "flagged"
    else:
        status = "safe"

    return {"status": status, "matched_categories": sorted(set(categories))}


def assess_correction_safety(
    corrected_text: str, *, system_text: str | None, original_prompt_text: str | None
) -> dict[str, Any]:
    """A proposed corrected response must not itself introduce unsafe
    instructions, leak the system prompt, echo the original prompt back
    verbatim, or degenerate into excessive repetition."""

    base = assess_feedback_safety(
        corrected_text, system_text=system_text, user_text=original_prompt_text
    )
    repetition = no_excessive_repetition(corrected_text)
    issues = list(base["matched_categories"])
    if repetition["status"] == "warning":
        issues.append("repetition")
    status = base["status"]
    if status == "safe" and "repetition" in issues:
        status = "flagged"
    return {"status": status, "matched_categories": sorted(set(issues))}


def classify_injection_for_feedback(text: str, *, policy: str = "block") -> str:
    signals = detect_injection_signals(text)
    return classify_injection_status(signals["matched_categories"], policy=policy)
