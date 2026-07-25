"""Deterministic feedback triage.

Priority is a documented, rule-based computation over explicit signals
-- never an opaque ML ranking. Given the same inputs, the same
priority and queue routing are produced every time.
"""

from __future__ import annotations

from core_model.feedback import CRITICAL_CLASSIFICATION_CATEGORIES, SEVERITIES

_SEVERITY_RANK = {name: index for index, name in enumerate(SEVERITIES)}

_QUEUE_ROUTING = {
    "poor_tamil": "tamil_quality",
    "poor_tanglish": "tanglish_quality",
    "wrong_language": "language",
    "citation_missing": "citation",
    "citation_invalid": "citation",
    "citation_wrong": "citation",
    "retrieval_irrelevant": "retrieval",
    "retrieval_missing": "retrieval",
    "unsafe_response": "safety",
    "over_refusal": "safety",
    "under_refusal": "safety",
    "prompt_leakage": "safety",
    "role_token_leakage": "safety",
    "memory_wrong": "memory",
    "memory_outdated": "memory",
    "memory_privacy_issue": "privacy",
    "memory_not_used": "memory",
    "memory_should_not_be_used": "privacy",
}


def route_to_queue_type(categories: list[str]) -> str:
    """First matching category wins, in the fixed order below --
    deterministic, not a priority race. Falls back to
    ``general_quality`` when nothing more specific applies."""

    for category in categories:
        if category in _QUEUE_ROUTING:
            return _QUEUE_ROUTING[category]
    return "general_quality"


def compute_priority(
    *,
    severity: str,
    categories: list[str],
    privacy_status: str,
    safety_status: str,
    rating: int | None,
    similar_open_feedback_count: int,
    is_regression_recurrence: bool,
) -> str:
    """Returns one of the 5 severity levels as the assignment priority.
    Rules applied in fixed order, most severe first:

    1. Blocked privacy/safety -> critical.
    2. Any always-critical category -> critical.
    3. Explicit severity, if at or above the computed floor.
    4. Regression recurrence bumps the floor to at least ``high``.
    5. High frequency (3+ similar open items) bumps the floor to at
       least ``medium``.
    6. A 1-star rating bumps the floor to at least ``medium``.
    """

    if privacy_status == "blocked" or safety_status == "blocked":
        return "critical"
    if any(category in CRITICAL_CLASSIFICATION_CATEGORIES for category in categories):
        return "critical"

    floor = "info"
    if is_regression_recurrence:
        floor = "high"
    elif similar_open_feedback_count >= 3 or rating == 1:
        floor = "medium"

    explicit = severity if severity in _SEVERITY_RANK else "info"
    return explicit if _SEVERITY_RANK[explicit] >= _SEVERITY_RANK[floor] else floor


def requires_priority_review(priority: str) -> bool:
    return priority == "critical"
