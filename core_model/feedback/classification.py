"""Feedback classification helpers.

A feedback event may carry multiple classifications (e.g. both
``citation_missing`` and ``poor_tamil``); each classification is its
own append-only row, never a single overloaded status field.
"""

from __future__ import annotations

from core_model.feedback import (
    CLASSIFICATION_CATEGORIES,
    CRITICAL_CLASSIFICATION_CATEGORIES,
    SEVERITIES,
)


def validate_classification(category: str, severity: str) -> tuple[bool, str | None]:
    if category not in CLASSIFICATION_CATEGORIES:
        return False, "unsupported_classification_category"
    if severity not in SEVERITIES:
        return False, "unsupported_severity"
    return True, None


def is_critical(category: str, severity: str) -> bool:
    """A classification is critical if the admin/reviewer explicitly
    marked it ``critical`` OR it belongs to a category that is always
    safety-critical regardless of the assigned severity (never rely on
    severity alone for categories like ``unsafe_response``)."""

    return severity == "critical" or category in CRITICAL_CLASSIFICATION_CATEGORIES


def language_related_categories(categories: list[str]) -> list[str]:
    return [
        category
        for category in categories
        if category in {"wrong_language", "poor_tamil", "poor_tanglish"}
    ]


def citation_related_categories(categories: list[str]) -> list[str]:
    return [
        category
        for category in categories
        if category in {"citation_missing", "citation_invalid", "citation_wrong"}
    ]


def retrieval_related_categories(categories: list[str]) -> list[str]:
    return [
        category
        for category in categories
        if category in {"retrieval_irrelevant", "retrieval_missing"}
    ]


def memory_related_categories(categories: list[str]) -> list[str]:
    return [
        category
        for category in categories
        if category
        in {
            "memory_wrong",
            "memory_outdated",
            "memory_privacy_issue",
            "memory_not_used",
            "memory_should_not_be_used",
        }
    ]


def safety_related_categories(categories: list[str]) -> list[str]:
    return [
        category
        for category in categories
        if category
        in {
            "unsafe_response",
            "over_refusal",
            "under_refusal",
            "prompt_leakage",
            "role_token_leakage",
        }
    ]
