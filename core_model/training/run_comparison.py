"""Compatibility-aware comparison between two pretraining run profiles."""

from __future__ import annotations

from typing import Any

COMPATIBLE = "compatible"
PARTIALLY_COMPATIBLE = "partially_compatible"
INCOMPATIBLE = "incompatible"

_COMPARED_FIELDS = (
    "dataset_version_public_id",
    "tokenizer_version_public_id",
    "core_model_config_public_id",
    "initialization_seed",
    "sampling_seed",
    "sequence_length",
    "total_steps",
    "completed_steps",
    "processed_tokens",
    "initial_training_loss",
    "final_training_loss",
    "final_validation_loss",
    "final_perplexity",
    "average_tokens_per_second",
    "peak_process_memory_bytes",
    "pause_count",
    "resume_count",
    "recovery_count",
    "coverage_ratio",
    "quality_overall_score",
    "quality_readiness_status",
)


def _compatibility(left: dict[str, Any], right: dict[str, Any]) -> str:
    if left.get("tokenizer_version_public_id") != right.get("tokenizer_version_public_id"):
        return INCOMPATIBLE
    if left.get("core_model_config_public_id") != right.get("core_model_config_public_id"):
        return INCOMPATIBLE
    if left.get("dataset_version_public_id") != right.get("dataset_version_public_id"):
        return PARTIALLY_COMPATIBLE
    return COMPATIBLE


def compare_runs(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    compatibility = _compatibility(left, right)
    fields = {
        field: {"left": left.get(field), "right": right.get(field)} for field in _COMPARED_FIELDS
    }
    return {
        "compatibility": compatibility,
        "ranked": compatibility == COMPATIBLE,
        "fields": fields,
    }
