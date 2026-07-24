"""Evaluation-run comparison compatibility and field diffing.

This is genuinely new logic (not reused from Phase 10's
``TrainingEvaluationService.compare_runs``, which compares
``pretraining_jobs``, a different entity) but mirrors the same
compatibility-level + field-diff shape Phase 10/11/12 already established.
"""

from __future__ import annotations

COMPATIBLE = "compatible"
PARTIALLY_COMPATIBLE = "partially_compatible"
INCOMPATIBLE = "incompatible"


def assess_compatibility(left: dict, right: dict) -> str:
    """Direct ranking requires identical suite version, generation config,
    tokenizer, fixture set, and threshold configuration."""

    hard_fields = (
        "suite_version_public_id", "generation_config_checksum_sha256",
        "tokenizer_version_public_id", "fixture_set_checksum_sha256",
        "threshold_configuration_checksum_sha256",
    )
    if all(left.get(field) == right.get(field) for field in hard_fields):
        return COMPATIBLE
    soft_fields = ("suite_version_public_id", "tokenizer_version_public_id")
    if all(left.get(field) == right.get(field) for field in soft_fields):
        return PARTIALLY_COMPATIBLE
    return INCOMPATIBLE


def build_field_diff(left: dict, right: dict, fields: list[str]) -> dict:
    return {field: {"left": left.get(field), "right": right.get(field)} for field in fields}


def compare_runs(left: dict, right: dict, diff_fields: list[str]) -> dict:
    compatibility = assess_compatibility(left, right)
    return {
        "compatibility": compatibility,
        "ranked": compatibility == COMPATIBLE,
        "fields": build_field_diff(left, right, diff_fields),
    }
