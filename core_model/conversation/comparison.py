"""Deterministic comparison of two memory retrieval profiles or
evaluation runs, mirroring the compatibility-level + field-diff shape
already established in Phase 10-16."""

from __future__ import annotations

from typing import Any

HARD_FIELDS = ("keyword_weight", "vector_weight")
SOFT_FIELDS = ("conflict_policy", "maximum_results")
COMPARISON_FIELDS = HARD_FIELDS + SOFT_FIELDS + (
    "recency_weight", "user_confirmed_boost", "minimum_score",
)


def build_field_diff(
    left: dict[str, Any], right: dict[str, Any], fields: tuple[str, ...]
) -> dict[str, Any]:
    diff = {}
    for field_name in fields:
        left_value = left.get(field_name)
        right_value = right.get(field_name)
        diff[field_name] = {
            "left": left_value, "right": right_value, "matches": left_value == right_value,
        }
    return diff


def assess_compatibility(left: dict[str, Any], right: dict[str, Any]) -> str:
    if all(left.get(field_name) == right.get(field_name) for field_name in HARD_FIELDS):
        return "compatible"
    if all(left.get(field_name) == right.get(field_name) for field_name in SOFT_FIELDS):
        return "partially_compatible"
    return "incompatible"


def compare_profiles(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    compatibility = assess_compatibility(left, right)
    diff = build_field_diff(left, right, COMPARISON_FIELDS)
    return {"compatibility": compatibility, "fields": diff}
