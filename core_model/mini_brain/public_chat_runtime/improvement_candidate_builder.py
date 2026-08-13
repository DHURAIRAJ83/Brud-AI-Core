"""MB-23: Improvement Candidate Builder -- pure. Turns one already-
built failure cluster into a candidate record, born with
`status='pending_admin_review'` (enforced at the repository/schema
layer, not here) -- this module only computes an `impact_score` and a
`recommended_action` key from the cluster's own already-counted
signal severities and types; it never approves, creates, or starts
anything in any other phase.
"""

from __future__ import annotations

from typing import Any

_SEVERITY_WEIGHTS = {"low": 1.0, "medium": 2.0, "high": 3.0}

# Maps the cluster's dominant signal type to an advisory next action --
# never an instruction to actually perform that action.
_ACTION_BY_SIGNAL_TYPE = {
    "explicit_negative": "mb13_cleanup",
    "low_confidence": "mb16_dataset_draft",
    "insufficient_evidence": "mb16_dataset_draft",
    "repeated_question": "mb18_package_refresh",
    "clarification_needed": "mb13_cleanup",
    "safety_flag": "mb21_external_evaluation",
}


def compute_impact_score(*, severity_counts: dict[str, int]) -> float:
    return round(sum(_SEVERITY_WEIGHTS.get(severity, 0.0) * count for severity, count in severity_counts.items()), 3)


def dominant_signal_type(*, signal_type_counts: dict[str, int]) -> str:
    if not signal_type_counts:
        return "unclassified"
    return max(sorted(signal_type_counts), key=lambda t: signal_type_counts[t])


def recommend_action(*, signal_type: str) -> str:
    return _ACTION_BY_SIGNAL_TYPE.get(signal_type, "mb13_cleanup")


def build_candidate(*, cluster: dict[str, Any]) -> dict[str, Any]:
    impact_score = compute_impact_score(severity_counts=cluster["severity_counts"])
    dominant = dominant_signal_type(signal_type_counts=cluster["signal_type_counts"])
    action = recommend_action(signal_type=dominant)
    topic = cluster["topic_key"].title() if cluster["topic_key"] != "unclassified" else "Unclassified Topic"
    return {
        "topic": topic, "topic_key": cluster["topic_key"], "frequency": cluster["frequency"],
        "impact_score": impact_score, "recommended_action": action,
        "example_questions": cluster["example_texts"],
        "suggested_missing_knowledge": {
            "topic_key": cluster["topic_key"], "dominant_signal_type": dominant,
            "distinct_session_count": cluster["distinct_session_count"],
            "note": "heuristic topic grouping only -- an admin must verify the actual knowledge gap before acting",
        },
        "status": "pending_admin_review",
        "disclosure": "impact_score is a fixed severity-weighted sum, and recommended_action is a fixed lookup from the cluster's dominant signal type -- neither is a calibrated model",
    }
