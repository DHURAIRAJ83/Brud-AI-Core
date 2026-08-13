"""Confidence Calculator -- deterministic point-based scoring, no
probability model, no learned weights. Every contribution below is a
fixed constant applied when a specific, already-computed condition is
true; the total is clamped to 0-100 and banded into
high/medium/low/none.
"""

from __future__ import annotations

from typing import Any

_BASE_PER_KEYWORD_HIT = 15
_BASE_CAP = 45
_PRIMARY_KNOWLEDGE_BONUS = 30
_SUPPORTING_KNOWLEDGE_BONUS = 15
_WORKFLOW_CHAIN_BONUS = 10
_UNKNOWN_INTENT_PENALTY = 40
_INSUFFICIENT_KNOWLEDGE_PENALTY = 30
_NEEDS_CLARIFICATION_PENALTY = 20


def calculate_confidence(
    *, intent_confidence_signal: int, intent: str, knowledge_plan: dict[str, Any],
    workflow: dict[str, Any], rule_flags: list[str],
) -> dict[str, Any]:
    score = min(intent_confidence_signal * _BASE_PER_KEYWORD_HIT, _BASE_CAP)
    contributions = [{"reason": "intent_keyword_match", "points": score}]

    if knowledge_plan["primary_knowledge"]:
        score += _PRIMARY_KNOWLEDGE_BONUS
        contributions.append({"reason": "primary_knowledge_found", "points": _PRIMARY_KNOWLEDGE_BONUS})
    if knowledge_plan["supporting_knowledge"]:
        score += _SUPPORTING_KNOWLEDGE_BONUS
        contributions.append({"reason": "supporting_knowledge_found", "points": _SUPPORTING_KNOWLEDGE_BONUS})
    if workflow.get("in_a_workflow_chain"):
        score += _WORKFLOW_CHAIN_BONUS
        contributions.append({"reason": "workflow_chain_resolved", "points": _WORKFLOW_CHAIN_BONUS})
    if intent == "unknown":
        score -= _UNKNOWN_INTENT_PENALTY
        contributions.append({"reason": "unknown_intent", "points": -_UNKNOWN_INTENT_PENALTY})
    if "insufficient_knowledge" in rule_flags:
        score -= _INSUFFICIENT_KNOWLEDGE_PENALTY
        contributions.append({"reason": "insufficient_knowledge", "points": -_INSUFFICIENT_KNOWLEDGE_PENALTY})
    if "needs_clarification" in rule_flags:
        score -= _NEEDS_CLARIFICATION_PENALTY
        contributions.append({"reason": "needs_clarification", "points": -_NEEDS_CLARIFICATION_PENALTY})

    score = max(0, min(100, score))
    if score >= 70:
        band = "high"
    elif score >= 40:
        band = "medium"
    elif score > 0:
        band = "low"
    else:
        band = "none"

    return {"score": score, "band": band, "contributions": contributions}
