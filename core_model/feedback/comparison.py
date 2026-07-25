"""Deterministic regression-run compatibility and model-comparison
classification.

Mirrors the compatibility-level + field-diff shape already established
by ``core_model.rag.comparison`` (Phase 16) and
``model_evaluation_comparisons`` (Phase 13). Direct ranking requires
the exact same regression suite and generation configuration -- an
admin can trust "improved"/"regressed" only when both runs were scored
against identical evidence.
"""

from __future__ import annotations

from typing import Any

HARD_FIELDS = ("regression_suite_checksum", "generation_configuration_checksum")
SOFT_FIELDS = ("assignment_scope", "rag_retrieval_profile_public_id", "memory_policy_public_id")
COMPARISON_FIELDS = HARD_FIELDS + SOFT_FIELDS


def build_field_diff(
    left: dict[str, Any], right: dict[str, Any], fields: tuple[str, ...] = COMPARISON_FIELDS
) -> dict[str, Any]:
    diff = {}
    for field_name in fields:
        left_value = left.get(field_name)
        right_value = right.get(field_name)
        diff[field_name] = {
            "left": left_value,
            "right": right_value,
            "matches": left_value == right_value,
        }
    return diff


def assess_compatibility(left: dict[str, Any], right: dict[str, Any]) -> str:
    if all(left.get(field_name) == right.get(field_name) for field_name in HARD_FIELDS):
        return "compatible"
    if all(left.get(field_name) == right.get(field_name) for field_name in SOFT_FIELDS):
        return "partially_compatible"
    return "incompatible"


def classify_comparison_result(
    *,
    compatibility: str,
    fixed_failure_rate: float | None,
    new_regression_rate: float | None,
    persistent_failure_rate: float | None,
) -> str:
    """Never produces a ranking claim for incompatible evidence."""

    if compatibility == "incompatible":
        return "incomparable"
    if fixed_failure_rate is None or new_regression_rate is None:
        return "incomparable"
    improved = fixed_failure_rate > 0 and new_regression_rate == 0
    regressed = new_regression_rate > 0 and fixed_failure_rate == 0
    if improved and not regressed:
        return "improved"
    if regressed and not improved:
        return "regressed"
    if fixed_failure_rate == 0 and new_regression_rate == 0:
        return "unchanged"
    return "mixed"
