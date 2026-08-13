"""MB-19: Regression Comparator -- pure. Compares a flat metric-name to
value mapping from the current run against a previous approved
evaluation session's own stored mapping. Reports improved/regressed/
unchanged metrics, an overall drift score, and a release risk level --
deliberately never an automatic pass/fail, matching the task spec's
own Step 9 requirement.

Every value in `current_metrics`/`baseline_metrics` must already be on
a comparable 0-1 scale (a ratio, not a 0-100 composite score) --
`overall_drift_score` is a plain sum of deltas, so mixing scales would
make `HIGH_RISK_DRIFT_THRESHOLD` meaningless. The caller (the service
layer) is responsible for normalizing any 0-100 score to 0-1 before
building these dicts.
"""

from __future__ import annotations

from typing import Any

UNCHANGED_EPSILON = 0.001
HIGH_RISK_DRIFT_THRESHOLD = 0.1


def compare_against_baseline(
    *, current_metrics: dict[str, float | None], baseline_metrics: dict[str, float | None] | None,
) -> dict[str, Any]:
    if not baseline_metrics:
        return {
            "has_baseline": False, "improved_metrics": [], "regressed_metrics": [], "unchanged_metrics": [],
            "missing_baseline_metrics": sorted(current_metrics), "overall_drift_score": None,
            "release_risk_level": "unknown",
            "disclosure": "no previous approved evaluation session exists yet -- this is the first baseline, not a regression",
        }

    improved: list[dict[str, Any]] = []
    regressed: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []
    missing_baseline: list[str] = []

    for name, current_value in current_metrics.items():
        baseline_value = baseline_metrics.get(name)
        if baseline_value is None:
            missing_baseline.append(name)
            continue
        if current_value is None:
            continue
        delta = round(current_value - baseline_value, 4)
        entry = {"metric": name, "baseline": baseline_value, "current": current_value, "delta": delta}
        if abs(delta) < UNCHANGED_EPSILON:
            unchanged.append(entry)
        elif delta > 0:
            improved.append(entry)
        else:
            regressed.append(entry)

    drift_score = round(sum(abs(entry["delta"]) for entry in regressed), 4)
    if not regressed:
        risk_level = "low"
    elif drift_score > HIGH_RISK_DRIFT_THRESHOLD or len(regressed) > len(improved):
        risk_level = "high"
    else:
        risk_level = "medium"

    return {
        "has_baseline": True,
        "improved_metrics": improved, "regressed_metrics": regressed, "unchanged_metrics": unchanged,
        "missing_baseline_metrics": missing_baseline,
        "overall_drift_score": drift_score, "release_risk_level": risk_level,
        "disclosure": (
            "no automatic pass/fail is applied here -- release_risk_level is informational only, "
            "read by release_readiness_evaluator.py as one signal among several, never the sole decider"
        ),
    }
