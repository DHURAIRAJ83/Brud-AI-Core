"""Deterministic validation for a bounded local inference runtime profile.

Phase 15 targets low-memory CPU-only hardware: one loaded model, one
active generation, float32, batch size 1. This module only validates the
declared bounds — it never measures actual hardware itself (see
``resource_guard.py`` for that).
"""

from __future__ import annotations

from core_model.inference_runtime import ALLOWED_DTYPES, RUNTIME_TYPES


def validate_runtime_profile(
    *,
    runtime_type: str,
    dtype: str,
    maximum_loaded_models: int,
    maximum_concurrent_requests: int,
    maximum_context_length: int,
    maximum_new_tokens: int,
    request_timeout_seconds: int,
    idle_unload_seconds: int,
    minimum_available_memory_bytes: int,
    minimum_available_disk_bytes: int,
) -> list[str]:
    """Returns a list of validation error messages; empty means valid."""

    errors: list[str] = []
    if runtime_type not in RUNTIME_TYPES:
        errors.append(f"runtime_type must be one of {RUNTIME_TYPES}")
    if dtype not in ALLOWED_DTYPES:
        errors.append(f"dtype must be one of {ALLOWED_DTYPES}")
    if maximum_loaded_models < 1:
        errors.append("maximum_loaded_models must be at least 1")
    if maximum_concurrent_requests < 1:
        errors.append("maximum_concurrent_requests must be at least 1")
    if maximum_context_length < 8:
        errors.append("maximum_context_length must be at least 8")
    if maximum_new_tokens < 1:
        errors.append("maximum_new_tokens must be at least 1")
    if maximum_new_tokens > maximum_context_length:
        errors.append("maximum_new_tokens must not exceed maximum_context_length")
    if request_timeout_seconds < 1:
        errors.append("request_timeout_seconds must be at least 1")
    if idle_unload_seconds < 1:
        errors.append("idle_unload_seconds must be at least 1")
    if minimum_available_memory_bytes < 0:
        errors.append("minimum_available_memory_bytes must not be negative")
    if minimum_available_disk_bytes < 0:
        errors.append("minimum_available_disk_bytes must not be negative")
    return errors
