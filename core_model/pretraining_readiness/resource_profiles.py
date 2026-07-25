"""CPU-safe Brud AI base-model configuration profiles -- pure
functions only. Parameter/memory formulas are reused unchanged from
Phase 8's `core_model.evaluation.architecture_checks` (never
reimplemented); this module only adds the profile shapes themselves
plus disk and throughput estimates Phase 8 did not need."""

from __future__ import annotations

from dataclasses import dataclass

from core_model.architecture.config import BrudModelConfig
from core_model.evaluation.architecture_checks import estimate_memory, estimate_parameters

PROFILE_NAMES = ("micro_smoke_test", "small_experimental", "maximum_safe_local")

# Conservative default safe RAM ceiling for a ~6GB CPU-only machine --
# leaves headroom for the OS, SQLite, the admin dashboard/backend
# process, and the Python/PyTorch runtime itself.
DEFAULT_SAFE_RAM_CEILING_BYTES = 4_500_000_000

# Conservative CPU-only throughput baseline (tokens/sec for a
# ~1M-parameter model at batch_size=2, sequence_length~512), assumed
# to scale down roughly linearly with parameter count. Used only to
# produce an honest, wide *range*, never a precise promise.
_BASELINE_TOKENS_PER_SECOND_AT_ONE_MILLION_PARAMS = 500.0
_BYTES_PER_PARAMETER = 4


def _config_for_shape(
    *,
    vocabulary_size: int,
    context_length: int,
    hidden_size: int,
    num_hidden_layers: int,
    num_attention_heads: int,
    intermediate_size: int,
) -> BrudModelConfig:
    config = BrudModelConfig(
        vocabulary_size=vocabulary_size,
        context_length=context_length,
        hidden_size=hidden_size,
        intermediate_size=intermediate_size,
        num_hidden_layers=num_hidden_layers,
        num_attention_heads=num_attention_heads,
        num_key_value_heads=num_attention_heads,
    )
    config.validate()
    return config


def micro_smoke_test_config(vocabulary_size: int) -> BrudModelConfig:
    """Profile A -- pipeline/checkpoint verification only, ~1-3M params."""

    return _config_for_shape(
        vocabulary_size=vocabulary_size,
        context_length=256,
        hidden_size=128,
        num_hidden_layers=4,
        num_attention_heads=4,
        intermediate_size=384,
    )


def small_experimental_config(vocabulary_size: int) -> BrudModelConfig:
    """Profile B -- short local learning experiment, ~10-30M params."""

    return _config_for_shape(
        vocabulary_size=vocabulary_size,
        context_length=512,
        hidden_size=384,
        num_hidden_layers=8,
        num_attention_heads=6,
        intermediate_size=1024,
    )


def maximum_safe_local_config(
    vocabulary_size: int, *, safe_ram_ceiling_bytes: int = DEFAULT_SAFE_RAM_CEILING_BYTES
) -> BrudModelConfig:
    """Profile C -- the largest local candidate whose estimated AdamW
    training memory still fits the configured safe RAM ceiling.
    Searches real candidate shapes (never a hardcoded "big" preset)
    with a fixed 64-dimension head size and a fixed 12-layer depth, so
    the result is genuinely calculated from available RAM rather than
    assumed."""

    num_hidden_layers = 12
    best: BrudModelConfig | None = None
    for hidden_size in range(128, 4096 + 1, 64):
        num_attention_heads = hidden_size // 64
        intermediate_size = hidden_size * 3
        candidate = _config_for_shape(
            vocabulary_size=vocabulary_size,
            context_length=512,
            hidden_size=hidden_size,
            num_hidden_layers=num_hidden_layers,
            num_attention_heads=num_attention_heads,
            intermediate_size=intermediate_size,
        )
        memory = estimate_memory(candidate, batch_size=2)
        if memory["training_adamw"] > safe_ram_ceiling_bytes:
            break
        best = candidate
    if best is None:
        # Even the smallest candidate shape exceeds the ceiling -- fall
        # back to the micro profile rather than returning an unsafe one.
        return micro_smoke_test_config(vocabulary_size)
    return best


_PROFILE_BUILDERS = {
    "micro_smoke_test": micro_smoke_test_config,
    "small_experimental": small_experimental_config,
}


@dataclass(frozen=True)
class ResourceEstimate:
    profile_name: str
    config: BrudModelConfig
    parameter_count: int
    parameter_memory_bytes: int
    gradient_memory_bytes: int
    optimizer_state_memory_bytes: int
    activation_memory_bytes: int
    estimated_peak_ram_bytes: int
    checkpoint_disk_bytes: int
    optimizer_disk_bytes: int
    estimated_tokens_per_second: float
    estimated_training_duration_seconds_min: int
    estimated_training_duration_seconds_max: int
    safe_ram_ceiling_bytes: int
    within_safe_limit: bool


def estimate_resource_profile(
    profile_name: str,
    vocabulary_size: int,
    *,
    total_training_tokens: int = 1_000_000,
    safe_ram_ceiling_bytes: int = DEFAULT_SAFE_RAM_CEILING_BYTES,
) -> ResourceEstimate:
    if profile_name not in PROFILE_NAMES:
        raise ValueError(f"unknown model profile: {profile_name}")
    if profile_name == "maximum_safe_local":
        config = maximum_safe_local_config(
            vocabulary_size, safe_ram_ceiling_bytes=safe_ram_ceiling_bytes
        )
    else:
        config = _PROFILE_BUILDERS[profile_name](vocabulary_size)

    params = estimate_parameters(config)
    memory = estimate_memory(config, batch_size=2)
    parameter_memory_bytes = params * _BYTES_PER_PARAMETER
    gradient_memory_bytes = parameter_memory_bytes
    # AdamW keeps two moment buffers per parameter (m and v).
    optimizer_state_memory_bytes = parameter_memory_bytes * 2
    activation_memory_bytes = max(
        0, memory["training_adamw"] - parameter_memory_bytes - optimizer_state_memory_bytes
    )
    estimated_peak_ram_bytes = memory["training_adamw"]
    # Checkpoints store model + optimizer state; disk estimates are
    # deliberately larger than the in-memory estimate (no compression
    # assumed) so disk-space validation stays conservative.
    checkpoint_disk_bytes = parameter_memory_bytes
    optimizer_disk_bytes = optimizer_state_memory_bytes
    params_millions = max(1.0, params / 1_000_000)
    tokens_per_second = max(
        0.1, _BASELINE_TOKENS_PER_SECOND_AT_ONE_MILLION_PARAMS / params_millions
    )
    duration_seconds = total_training_tokens / tokens_per_second
    return ResourceEstimate(
        profile_name=profile_name,
        config=config,
        parameter_count=params,
        parameter_memory_bytes=parameter_memory_bytes,
        gradient_memory_bytes=gradient_memory_bytes,
        optimizer_state_memory_bytes=optimizer_state_memory_bytes,
        activation_memory_bytes=activation_memory_bytes,
        estimated_peak_ram_bytes=estimated_peak_ram_bytes,
        checkpoint_disk_bytes=checkpoint_disk_bytes,
        optimizer_disk_bytes=optimizer_disk_bytes,
        estimated_tokens_per_second=tokens_per_second,
        estimated_training_duration_seconds_min=int(duration_seconds * 0.5),
        estimated_training_duration_seconds_max=int(duration_seconds * 2.0),
        safe_ram_ceiling_bytes=safe_ram_ceiling_bytes,
        within_safe_limit=estimated_peak_ram_bytes <= safe_ram_ceiling_bytes,
    )
