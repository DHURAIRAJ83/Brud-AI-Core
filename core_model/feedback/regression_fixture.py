"""Regression fixture construction.

Regression fixtures are evaluation-only evidence -- this module never
produces anything resembling a training record (no
``metadata_checksum``/dataset-candidate shape), and always screens
fixture text through the same privacy scan feedback content goes
through, since fixtures are quoted directly in future evaluation runs
and admin dashboards.
"""

from __future__ import annotations

from typing import Any

from core_model.feedback.privacy_filter import assess_feedback_privacy
from core_model.rag.text_normalization import content_checksum


def build_regression_fixture(
    *,
    category: str,
    language: str,
    input_text: str,
    controlled_context: dict[str, Any],
    expected_behavior: str,
    forbidden_behavior: str | None,
    expected_citations: list[str],
    expected_memory_behavior: dict[str, Any],
    severity: str,
    source_feedback_event_public_ids: list[str],
) -> dict[str, Any]:
    """Returns the fixture payload plus a validation outcome. Raises no
    exception -- the caller decides how to react to ``blocked``."""

    privacy = assess_feedback_privacy(input_text)
    checksum_source = "|".join(
        [
            category,
            language,
            input_text,
            expected_behavior,
            forbidden_behavior or "",
        ]
    )
    checksum = content_checksum(checksum_source)
    return {
        "category": category,
        "language": language,
        "input_text": input_text,
        "controlled_context": controlled_context,
        "expected_behavior": expected_behavior,
        "forbidden_behavior": forbidden_behavior,
        "expected_citations": expected_citations,
        "expected_memory_behavior": expected_memory_behavior,
        "severity": severity,
        "source_feedback_event_public_ids": source_feedback_event_public_ids,
        "checksum_sha256": checksum,
        "privacy_status": privacy["status"],
        "blocked": privacy["status"] == "blocked",
    }


def evaluate_fixture_result(
    *, actual_behavior_matches_expected: bool, forbidden_behavior_observed: bool
) -> dict[str, Any]:
    """A fixture only passes if the expected behavior was observed AND
    no forbidden behavior occurred -- either failure alone fails it."""

    passed = actual_behavior_matches_expected and not forbidden_behavior_observed
    if not actual_behavior_matches_expected and forbidden_behavior_observed:
        reason = "expected_behavior_missing_and_forbidden_behavior_observed"
    elif not actual_behavior_matches_expected:
        reason = "expected_behavior_missing"
    elif forbidden_behavior_observed:
        reason = "forbidden_behavior_observed"
    else:
        reason = None
    return {"passed": passed, "failure_reason": reason}
