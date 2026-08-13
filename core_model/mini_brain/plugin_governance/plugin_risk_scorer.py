"""MB-24: Plugin Risk Scorer -- pure. A fixed, disclosed heuristic
weighted sum over sensitivity counts, requested domain count, and two
elevated-risk flags -- never a calibrated statistical or ML model.
"""

from __future__ import annotations

from typing import Any

SENSITIVITY_WEIGHTS = {"low": 1.0, "medium": 3.0, "high": 7.0, "critical": 15.0}
DOMAIN_WEIGHT = 0.5
FILESYSTEM_WRITE_PENALTY = 5.0
CLOUD_STORAGE_PENALTY = 2.0

RISK_LEVEL_THRESHOLDS = (("critical", 30.0), ("high", 15.0), ("medium", 5.0))


def _risk_level_for_score(score: float) -> str:
    for level, threshold in RISK_LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return "low"


def compute_risk_score(
    *, sensitivity_counts: dict[str, int], domain_count: int, filesystem_write_requested: bool,
    cloud_storage_usage: bool,
) -> dict[str, Any]:
    base_score = sum(SENSITIVITY_WEIGHTS.get(level, 0.0) * count for level, count in sensitivity_counts.items())
    domain_score = domain_count * DOMAIN_WEIGHT
    filesystem_penalty = FILESYSTEM_WRITE_PENALTY if filesystem_write_requested else 0.0
    storage_penalty = CLOUD_STORAGE_PENALTY if cloud_storage_usage else 0.0

    total = round(base_score + domain_score + filesystem_penalty + storage_penalty, 3)
    return {
        "risk_score": total, "risk_level": _risk_level_for_score(total),
        "components": {
            "sensitivity_score": round(base_score, 3), "domain_score": round(domain_score, 3),
            "filesystem_write_penalty": filesystem_penalty, "cloud_storage_penalty": storage_penalty,
        },
        "disclosure": "a fixed, disclosed weighted heuristic -- never a calibrated statistical or ML risk model",
    }
