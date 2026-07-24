"""Release comparison — genuinely new logic, mirroring the same
compatibility-level + field-diff shape Phase 10/11/12/13 already
established for their own comparison tables, but comparing releases (not
pretraining jobs or evaluation runs).

Direct ranking requires comparable evaluation evidence: two releases
evaluated with different evaluation suites are never treated as
equivalent, even if every other field matches.
"""

from __future__ import annotations

from typing import Any

COMPATIBLE = "compatible"
PARTIALLY_COMPATIBLE = "partially_compatible"
INCOMPATIBLE = "incompatible"


def assess_compatibility(left: dict[str, Any], right: dict[str, Any]) -> str:
    hard_fields = (
        "tokenizer_version_public_id", "model_config_checksum_sha256",
        "evaluation_suite_public_id",
    )
    if all(left.get(field) == right.get(field) for field in hard_fields):
        return COMPATIBLE
    soft_fields = ("tokenizer_version_public_id",)
    if all(left.get(field) == right.get(field) for field in soft_fields):
        return PARTIALLY_COMPATIBLE
    return INCOMPATIBLE


def build_field_diff(
    left: dict[str, Any], right: dict[str, Any], fields: list[str]
) -> dict[str, Any]:
    return {field: {"left": left.get(field), "right": right.get(field)} for field in fields}


def compare_releases(
    left: dict[str, Any], right: dict[str, Any], diff_fields: list[str]
) -> dict[str, Any]:
    compatibility = assess_compatibility(left, right)
    ranked = (
        compatibility == COMPATIBLE
        and left.get("evaluation_suite_public_id") is not None
        and right.get("evaluation_suite_public_id") is not None
        and left.get("evaluation_suite_public_id") == right.get("evaluation_suite_public_id")
    )
    return {
        "compatibility": compatibility,
        "ranked": ranked,
        "fields": build_field_diff(left, right, diff_fields),
    }
