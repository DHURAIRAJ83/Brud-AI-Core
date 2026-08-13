"""MB-23: Priority Ranker -- pure. Computes a single `priority_score`
for one candidate from frequency, recency, unresolved rate, user
dissatisfaction, topic breadth, and a public-impact heuristic -- the
exact six factors the task spec's own Step 9 names. This is a fixed
weighted sum, disclosed as heuristic, never a calibrated statistical
or ML ranking model.
"""

from __future__ import annotations

from typing import Any

_WEIGHT_FREQUENCY = 1.0
_WEIGHT_RECENCY = 5.0
_WEIGHT_UNRESOLVED_RATE = 10.0
_WEIGHT_DISSATISFACTION = 10.0
_WEIGHT_TOPIC_BREADTH = 5.0
_WEIGHT_PUBLIC_IMPACT = 0.5


def compute_priority_score(
    *, frequency: int, distinct_session_count: int, most_recent_at_epoch_seconds: float,
    now_epoch_seconds: float, unresolved_rate: float, dissatisfaction_rate: float,
) -> dict[str, Any]:
    if frequency < 0 or distinct_session_count < 0:
        raise ValueError("frequency and distinct_session_count must be non-negative")
    if not (0.0 <= unresolved_rate <= 1.0) or not (0.0 <= dissatisfaction_rate <= 1.0):
        raise ValueError("unresolved_rate and dissatisfaction_rate must be within [0, 1]")

    recency_days = max(0.0, (now_epoch_seconds - most_recent_at_epoch_seconds) / 86_400.0)
    recency_weight = 1.0 / (1.0 + recency_days)
    topic_breadth = distinct_session_count / max(1, frequency)
    public_impact = float(distinct_session_count)

    components = {
        "frequency": frequency * _WEIGHT_FREQUENCY,
        "recency": recency_weight * _WEIGHT_RECENCY,
        "unresolved_rate": unresolved_rate * _WEIGHT_UNRESOLVED_RATE,
        "dissatisfaction": dissatisfaction_rate * _WEIGHT_DISSATISFACTION,
        "topic_breadth": topic_breadth * _WEIGHT_TOPIC_BREADTH,
        "public_impact": public_impact * _WEIGHT_PUBLIC_IMPACT,
    }
    priority_score = round(sum(components.values()), 4)
    return {
        "priority_score": priority_score, "components": {k: round(v, 4) for k, v in components.items()},
        "disclosure": "a fixed weighted sum over six named factors -- not a calibrated statistical or ML ranking model",
    }


def rank_candidates(*, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(candidates, key=lambda c: c["priority_score"], reverse=True)
