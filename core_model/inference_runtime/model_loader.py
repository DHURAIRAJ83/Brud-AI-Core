"""Deterministic pre-load compatibility checks for the inference runtime.

Path confinement is reused unchanged from Phase 14
(``core_model.release.artifact_inventory.resolve_confined_path``) rather
than re-implemented here — a release artifact is only ever loaded from an
approved, already-registered storage key, never an arbitrary path.
"""

from __future__ import annotations

from typing import Any

from core_model.inference_runtime import ASSIGNMENT_SCOPES, COMPATIBILITY_DIMENSIONS
from core_model.release.artifact_inventory import resolve_confined_path

__all__ = [
    "resolve_confined_path",
    "verify_vocabulary_compatibility",
    "missing_special_tokens",
    "LOAD_STEPS",
    "classify_load_outcome",
    "assess_runtime_compatibility",
]

LOAD_STEPS = (
    "manifest_verify",
    "artifact_verify",
    "checkpoint_verify",
    "tokenizer_verify",
    "model_config_verify",
    "resource_guard",
    "load_model",
    "runtime_health_check",
)


def verify_vocabulary_compatibility(
    model_vocabulary_size: int, tokenizer_vocabulary_size: int
) -> bool:
    return model_vocabulary_size == tokenizer_vocabulary_size


def missing_special_tokens(
    required_special_tokens: tuple[str, ...], tokenizer_special_tokens: list[str]
) -> list[str]:
    available = set(tokenizer_special_tokens)
    return [token for token in required_special_tokens if token not in available]


def classify_load_outcome(
    *,
    manifest_verified: bool,
    artifacts_verified: bool,
    checkpoint_verified: bool,
    tokenizer_verified: bool,
    model_config_matches: bool,
    resource_guard_passed: bool,
) -> tuple[str, str | None]:
    """Returns (status, failure_code) — status is 'ready' or 'failed'."""

    if not manifest_verified:
        return "failed", "manifest_mismatch"
    if not artifacts_verified:
        return "failed", "artifact_verification_failed"
    if not checkpoint_verified:
        return "failed", "checkpoint_corrupt"
    if not tokenizer_verified:
        return "failed", "tokenizer_invalid"
    if not model_config_matches:
        return "failed", "model_config_mismatch"
    if not resource_guard_passed:
        return "failed", "memory_guard_failed"
    return "ready", None


def assess_runtime_compatibility(
    *,
    release_manifest_verified: bool,
    checkpoint_verified: bool,
    tokenizer_verified: bool,
    vocabulary_compatible: bool,
    special_tokens_missing: list[str],
    model_config_matches: bool,
    requested_context_length: int,
    maximum_context_length: int,
    dtype: str,
    supported_dtypes: tuple[str, ...],
    device: str,
    supported_devices: tuple[str, ...],
    memory_compatible: bool,
    disk_compatible: bool,
    generation_policy_compatible: bool,
    evaluation_status: str,
    scope: str,
) -> dict[str, Any]:
    """Any integrity mismatch (release/checkpoint/tokenizer) is blocking,
    per Phase 15's compatibility rules; a `not_assessed`/`incompatible`
    dimension never silently downgrades to a warning."""

    dimension_scores: dict[str, str] = {
        "release_integrity": _status(release_manifest_verified),
        "checkpoint_integrity": _status(checkpoint_verified),
        "tokenizer_integrity": _status(tokenizer_verified),
        "vocabulary_compatibility": _status(vocabulary_compatible),
        "special_token_compatibility": _status(not special_tokens_missing),
        "model_config_compatibility": _status(model_config_matches),
        "context_compatibility": _status(requested_context_length <= maximum_context_length),
        "dtype_compatibility": _status(dtype in supported_dtypes),
        "device_compatibility": _status(device in supported_devices),
        "memory_compatibility": _status(memory_compatible),
        "disk_compatibility": _status(disk_compatible),
        "generation_policy_compatibility": _status(generation_policy_compatible),
        "evaluation_policy_compatibility": _status(
            evaluation_status not in {"evaluation_blocked", "not_assessed"}
        ),
        "assignment_scope_compatibility": _status(scope in ASSIGNMENT_SCOPES),
    }
    assert set(dimension_scores) == set(COMPATIBILITY_DIMENSIONS)
    blocking_issue_count = sum(
        1 for status in dimension_scores.values() if status == "incompatible"
    )
    status = "incompatible" if blocking_issue_count else "compatible"
    return {
        "status": status,
        "dimension_scores": dimension_scores,
        "blocking_issue_count": blocking_issue_count,
        "warning_issue_count": 0,
    }


def _status(ok: bool) -> str:
    return "compatible" if ok else "incompatible"
