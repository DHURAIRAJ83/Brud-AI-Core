"""MB-11: Dataset Quality Evolution -- pure. Predicts the quality,
coverage, training, and reasoning gain of the already-chosen expansion
action against the current advanced quality score, plus a disclosed
confidence and risk. A forward-looking prediction only -- never a
measurement of anything that has actually happened yet.
"""

from __future__ import annotations

from typing import Any

QUALITY_GAIN_BY_ACTION: dict[str, float] = {
    "extend": 5.0, "merge": 8.0, "create_new": 15.0, "split": 3.0, "replace": 20.0, "archive": 0.0,
}
RISK_BY_ACTION: dict[str, str] = {
    "extend": "Low", "merge": "Medium", "create_new": "Medium", "split": "Medium", "replace": "High", "archive": "Low",
}


def predict_quality_evolution(
    *,
    current_advanced_score: float,
    expansion_action: str,
    critical_gap_count: int,
    needs_expansion_count: int,
    knowledge_factory_content_types: list[str],
    growth_percent: float,
    cycles_compared: int,
) -> dict[str, Any]:
    quality_gain = QUALITY_GAIN_BY_ACTION.get(expansion_action, 0.0)
    predicted_quality_score = round(min(100.0, current_advanced_score + quality_gain), 1)

    coverage_gain = round(min(critical_gap_count * 6.0 + needs_expansion_count * 3.0, 40.0), 1)
    training_gain = round(min(abs(growth_percent) * 0.5, 30.0), 1)
    reasoning_gain = round(
        10.0 if any(t in {"Reasoning Tasks", "Exercises"} for t in knowledge_factory_content_types) else 2.0, 1,
    )

    confidence = round(min(50.0 + cycles_compared * 5.0, 90.0), 1)
    risk = RISK_BY_ACTION.get(expansion_action, "Medium")

    return {
        "current_quality_score": current_advanced_score,
        "predicted_quality_score": predicted_quality_score,
        "quality_gain": quality_gain,
        "coverage_gain": coverage_gain,
        "training_gain": training_gain,
        "reasoning_gain": reasoning_gain,
        "risk": risk,
        "confidence": confidence,
        "disclosure": "a heuristic projection from disclosed per-action gain tables, not a measured benchmark result",
    }
