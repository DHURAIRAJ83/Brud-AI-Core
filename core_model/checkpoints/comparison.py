"""Compatibility-aware comparison between two training checkpoints."""

from __future__ import annotations

from typing import Any

COMPATIBLE = "compatible"
PARTIALLY_COMPATIBLE = "partially_compatible"
INCOMPATIBLE = "incompatible"

_COMPARED_FIELDS = (
    "step",
    "processed_tokens",
    "training_loss",
    "validation_loss",
    "perplexity",
    "learning_rate",
    "checksum_status",
    "core_model_config_public_id",
    "dataset_version_public_id",
    "tokenizer_version_public_id",
    "file_size_bytes",
    "promotion_eligible",
)


def _compatibility(left: dict[str, Any], right: dict[str, Any]) -> str:
    if left.get("tokenizer_version_public_id") != right.get("tokenizer_version_public_id"):
        return INCOMPATIBLE
    if left.get("core_model_config_public_id") != right.get("core_model_config_public_id"):
        return INCOMPATIBLE
    if left.get("dataset_version_public_id") != right.get("dataset_version_public_id"):
        return PARTIALLY_COMPATIBLE
    return COMPATIBLE


def compare_checkpoints(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    compatibility = _compatibility(left, right)
    fields = {
        field: {"left": left.get(field), "right": right.get(field)} for field in _COMPARED_FIELDS
    }
    return {
        "compatibility": compatibility,
        "ranked": compatibility == COMPATIBLE,
        "fields": fields,
    }
