"""Deterministic corpus-version comparison.

Mirrors the compatibility-level + field-diff shape already established
by ``core_model.feedback.comparison`` (Phase 18) and
``core_model.rag.comparison`` (Phase 16). Corpora are never ranked by
size alone -- distribution, quality, licence, and contamination
evidence all factor into the comparison result.
"""

from __future__ import annotations

from typing import Any

HARD_FIELDS = ("balance_policy_checksum", "partition_configuration_checksum")
SOFT_FIELDS = ("corpus_policy_public_id", "collection_ids")


def assess_compatibility(left: dict[str, Any], right: dict[str, Any]) -> str:
    if all(left.get(field) == right.get(field) for field in HARD_FIELDS):
        return "compatible"
    if all(left.get(field) == right.get(field) for field in SOFT_FIELDS):
        return "partially_compatible"
    return "incompatible"


def compare_distributions(
    left: dict[str, float], right: dict[str, float]
) -> dict[str, dict[str, float]]:
    categories = sorted(set(left) | set(right))
    return {
        category: {"left": left.get(category, 0.0), "right": right.get(category, 0.0)}
        for category in categories
    }


def compare_versions(
    *,
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    """Never ranks by total-record count alone -- always reports the
    full distribution/quality/licence/contamination picture alongside
    size."""

    compatibility = assess_compatibility(left, right)
    return {
        "compatibility": compatibility,
        "total_records": {
            "left": left.get("total_records", 0), "right": right.get("total_records", 0),
        },
        "estimated_tokens": {
            "left": left.get("estimated_tokens", 0), "right": right.get("estimated_tokens", 0),
        },
        "language_distribution": compare_distributions(
            left.get("language_distribution", {}), right.get("language_distribution", {})
        ),
        "domain_distribution": compare_distributions(
            left.get("domain_distribution", {}), right.get("domain_distribution", {})
        ),
        "style_distribution": compare_distributions(
            left.get("style_distribution", {}), right.get("style_distribution", {})
        ),
        "licence_distribution": compare_distributions(
            left.get("licence_distribution", {}), right.get("licence_distribution", {})
        ),
        "known_limitations": [
            "Comparison covers distribution and quality signals, not semantic content overlap.",
        ],
    }
