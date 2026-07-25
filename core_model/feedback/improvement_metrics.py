"""Feedback and regression metrics.

Every rate here is an observed proportion of reviewed, structured
evidence -- never a claim that feedback alone proves correctness or
that a thumbs-up rate measures factual accuracy.
"""

from __future__ import annotations

from typing import Any


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def feedback_metrics(
    *,
    total_events: int,
    positive_events: int,
    negative_events: int,
    valid_verdicts: int,
    reviewed_verdicts: int,
    completed_reviews: int,
    total_assignments: int,
    critical_issue_count: int,
    privacy_blocked_count: int,
    safety_blocked_count: int,
    candidates_created: int,
    candidates_approved: int,
    regression_fixtures_created: int,
    review_durations_seconds: list[float],
) -> dict[str, Any]:
    median_review_time = None
    if review_durations_seconds:
        sorted_durations = sorted(review_durations_seconds)
        mid = len(sorted_durations) // 2
        median_review_time = (
            sorted_durations[mid]
            if len(sorted_durations) % 2
            else (sorted_durations[mid - 1] + sorted_durations[mid]) / 2
        )
    return {
        "feedback_submission_count": total_events,
        "positive_feedback_rate": _rate(positive_events, total_events),
        "negative_feedback_rate": _rate(negative_events, total_events),
        "valid_feedback_rate": _rate(valid_verdicts, reviewed_verdicts),
        "review_completion_rate": _rate(completed_reviews, total_assignments),
        "critical_issue_count": critical_issue_count,
        "privacy_block_rate": _rate(privacy_blocked_count, total_events),
        "safety_block_rate": _rate(safety_blocked_count, total_events),
        "candidate_conversion_rate": _rate(candidates_created, total_events),
        "candidate_approval_rate": _rate(candidates_approved, candidates_created),
        "regression_fixture_rate": _rate(regression_fixtures_created, total_events),
        "median_review_time_seconds": median_review_time,
    }


def regression_rates(
    *,
    baseline_results: dict[str, bool],
    candidate_results: dict[str, bool],
) -> dict[str, Any]:
    """``*_results`` map ``fixture_public_id -> passed``. A fixture
    present in only one run is excluded from the comparable set (never
    silently treated as fixed or as a new regression)."""

    shared_ids = set(baseline_results) & set(candidate_results)
    if not shared_ids:
        return {
            "fixed_failure_rate": None,
            "persistent_failure_rate": None,
            "new_regression_rate": None,
            "comparable_fixture_count": 0,
        }

    baseline_failures = {fid for fid in shared_ids if not baseline_results[fid]}
    fixed = {fid for fid in baseline_failures if candidate_results[fid]}
    persistent = {fid for fid in baseline_failures if not candidate_results[fid]}
    baseline_passes = shared_ids - baseline_failures
    new_regressions = {fid for fid in baseline_passes if not candidate_results[fid]}

    return {
        "fixed_failure_rate": _rate(len(fixed), len(baseline_failures)),
        "persistent_failure_rate": _rate(len(persistent), len(baseline_failures)),
        "new_regression_rate": _rate(len(new_regressions), len(baseline_passes)),
        "comparable_fixture_count": len(shared_ids),
    }


def category_regression_rate(
    *,
    baseline_results: dict[str, bool],
    candidate_results: dict[str, bool],
    fixture_categories: dict[str, str],
    category: str,
) -> float | None:
    ids = {fid for fid, cat in fixture_categories.items() if cat == category}
    shared = ids & set(baseline_results) & set(candidate_results)
    if not shared:
        return None
    regressions = sum(
        1
        for fid in shared
        if baseline_results[fid] and not candidate_results[fid]
    )
    return _rate(regressions, len(shared))
