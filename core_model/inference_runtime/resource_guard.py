"""Bounded, fail-closed resource guard for local CPU-only inference.

Every estimate is labelled ``estimated`` or ``measured`` and the label is
persisted verbatim — this module never claims a measured figure for a
value it only estimated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BYTES_PER_FLOAT32_PARAMETER = 4


def estimate_static_model_bytes(
    parameter_count: int, *, dtype_bytes: int = BYTES_PER_FLOAT32_PARAMETER
) -> int:
    """Model weights plus a bounded allowance for optimizer/buffer state."""

    return parameter_count * dtype_bytes


def estimate_peak_inference_bytes(
    *,
    static_model_bytes: int,
    context_length: int,
    hidden_size: int,
    num_hidden_layers: int,
    generation_length: int,
    dtype_bytes: int = BYTES_PER_FLOAT32_PARAMETER,
    safety_overhead_multiplier: float = 1.5,
) -> int:
    """Bounded estimate: static weights + activation/attention buffers for one
    batch-size-1 forward pass across the full context, times a safety margin."""

    sequence_span = context_length + generation_length
    activation_bytes = sequence_span * hidden_size * num_hidden_layers * dtype_bytes * 2
    attention_buffer_bytes = sequence_span * sequence_span * num_hidden_layers * dtype_bytes
    raw_peak = static_model_bytes + activation_bytes + attention_buffer_bytes
    return int(raw_peak * safety_overhead_multiplier)


@dataclass(frozen=True)
class ResourceAssessment:
    verdict: str  # "pass" | "fail"
    reasons: list[str] = field(default_factory=list)
    measurement_label: str = "estimated"


def assess_resource_guard(
    *,
    available_memory_bytes: int,
    available_disk_bytes: int,
    estimated_peak_inference_bytes: int,
    minimum_available_memory_bytes: int,
    minimum_available_disk_bytes: int,
    checkpoint_size_bytes: int,
    tokenizer_size_bytes: int,
    requested_context_length: int,
    maximum_context_length: int,
    requested_generation_limit: int,
    maximum_new_tokens: int,
    maximum_loaded_models: int,
    currently_loaded_model_count: int,
    maximum_concurrent_requests: int,
    currently_active_request_count: int,
    measurement_label: str = "estimated",
) -> ResourceAssessment:
    """Fail-closed: any single check failing fails the whole assessment."""

    reasons: list[str] = []

    if requested_context_length > maximum_context_length:
        reasons.append("requested context length exceeds runtime profile maximum")
    if requested_generation_limit > maximum_new_tokens:
        reasons.append("requested generation limit exceeds runtime profile maximum")
    if currently_loaded_model_count >= maximum_loaded_models:
        reasons.append("runtime already has the maximum number of loaded models")
    if currently_active_request_count >= maximum_concurrent_requests:
        reasons.append("runtime already has the maximum number of active requests")

    required_disk = checkpoint_size_bytes + tokenizer_size_bytes + minimum_available_disk_bytes
    if available_disk_bytes < required_disk:
        reasons.append("insufficient available disk space for checkpoint and tokenizer")

    required_memory = estimated_peak_inference_bytes + minimum_available_memory_bytes
    if available_memory_bytes < required_memory:
        reasons.append("insufficient available memory for the estimated peak inference footprint")

    return ResourceAssessment(
        verdict="pass" if not reasons else "fail",
        reasons=reasons,
        measurement_label=measurement_label,
    )
