"""MB-04A: post-generation response validation -- deterministic
substring/pattern checks only, never a second model call. Checks
language match, confidence-appropriate hedging, and self-claimed
rule-violating actions (training execution, admin actions the model
must never claim to have performed).
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.prompting.language_detector import detect_language, resolve_output_language

# Phrases that would mean the model is claiming to have taken an
# action it is never allowed to take -- mirrors the spirit of MB-03's
# Rule Engine training-boundary check, but applied to the model's
# OUTPUT text rather than the user's input question.
_SELF_CLAIMED_ACTION_PHRASES = (
    "i have started training", "i started training", "training has begun",
    "i will start the training", "i am executing", "i have executed",
    "i have deleted", "i have modified the dataset", "i granted access",
    "i have granted", "training is now running", "i have begun training",
    "i've started training", "i've executed",
)

_OVERCONFIDENT_PHRASES = ("definitely", "guaranteed", "100%", "always works", "certainly will")


def validate_response(
    text: str, *, expected_output_language: str, confidence_band: str,
) -> dict[str, Any]:
    issues: list[str] = []

    lang_analysis = detect_language(text)
    resolved_language = resolve_output_language(lang_analysis)
    if resolved_language != expected_output_language:
        issues.append(
            f"language_mismatch: expected {expected_output_language}, "
            f"response resolved to {resolved_language}"
        )

    lowered = text.lower()

    violated_actions = [p for p in _SELF_CLAIMED_ACTION_PHRASES if p in lowered]
    if violated_actions:
        issues.append(f"self_claimed_restricted_action: {violated_actions}")

    if confidence_band in ("none", "low"):
        overconfident = [p for p in _OVERCONFIDENT_PHRASES if p in lowered]
        if overconfident:
            issues.append(f"overconfident_despite_low_confidence: {overconfident}")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "language_analysis": lang_analysis,
        "resolved_language": resolved_language,
    }
