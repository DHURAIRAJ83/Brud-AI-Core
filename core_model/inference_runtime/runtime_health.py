"""Deterministic runtime health-check aggregation.

A runtime with a checkpoint mismatch, tokenizer mismatch, role-token
leakage during its generation smoke test, or a memory failure must never
become ``ready`` — this module enforces that as a hard rule, not a
heuristic the caller could accidentally override.
"""

from __future__ import annotations

from core_model.inference_runtime import HEALTH_CHECK_TYPES, HEALTH_STATUSES

_NEVER_READY_IF_UNHEALTHY = frozenset(
    {"checkpoint_verified", "tokenizer_loaded", "memory_available", "special_token_output_safe"}
)


def aggregate_health_status(check_results: dict[str, str]) -> str:
    """``check_results`` maps check_type -> status for all HEALTH_CHECK_TYPES."""

    for check_type in HEALTH_CHECK_TYPES:
        status = check_results.get(check_type)
        if status not in HEALTH_STATUSES:
            raise ValueError(f"missing or invalid status for check: {check_type}")

    if any(check_results[name] == "unhealthy" for name in _NEVER_READY_IF_UNHEALTHY):
        return "unhealthy"
    if any(status == "unhealthy" for status in check_results.values()):
        return "unhealthy"
    if any(status in ("degraded", "not_checked") for status in check_results.values()):
        return "degraded"
    return "healthy"


def instance_may_become_ready(check_results: dict[str, str]) -> bool:
    return aggregate_health_status(check_results) == "healthy"
