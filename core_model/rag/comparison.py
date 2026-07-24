"""Deterministic index/retrieval-configuration comparison.

Mirrors the compatibility-level + field-diff shape Phase 10-15 already
established. Direct ranking requires the same evaluation fixture set —
an admin can trust a side-by-side ranking only when both configurations
were scored against identical fixtures.
"""

from __future__ import annotations

from typing import Any

HARD_FIELDS = ("embedding_model_public_id", "distance_metric", "dimensions")
SOFT_FIELDS = ("chunking_strategy", "keyword_tokenizer")
COMPARISON_FIELDS = HARD_FIELDS + SOFT_FIELDS + (
    "vector_top_k",
    "keyword_top_k",
    "final_top_k",
    "vector_weight",
    "keyword_weight",
    "overlap_tokens",
)


def build_field_diff(
    left: dict[str, Any], right: dict[str, Any], fields: tuple[str, ...]
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


def compare_indexes(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    left_fixture_set_checksum: str | None,
    right_fixture_set_checksum: str | None,
) -> dict[str, Any]:
    compatibility = assess_compatibility(left, right)
    diff = build_field_diff(left, right, COMPARISON_FIELDS)
    ranked = (
        compatibility == "compatible"
        and left_fixture_set_checksum is not None
        and left_fixture_set_checksum == right_fixture_set_checksum
    )
    return {"compatibility": compatibility, "ranked": ranked, "fields": diff}
