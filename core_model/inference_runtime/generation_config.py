"""Bounded generation configuration: validated, deterministic by default.

Greedy decoding with sampling disabled is the only default anywhere in
Phase 15. Optional bounded ``top_k``/``temperature`` sampling may be
requested explicitly, but is never permitted for the ``public_chat``
scope regardless of what is requested.
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.inference_runtime import CONTEXT_TRUNCATION_POLICIES, DECODING_MODES


@dataclass(frozen=True)
class GenerationConfig:
    decoding_mode: str = "greedy"
    maximum_new_tokens: int = 32
    minimum_new_tokens: int = 0
    stop_at_eos: bool = True
    repetition_penalty: float | None = None
    top_k: int | None = None
    temperature: float | None = None
    request_timeout_seconds: int = 30
    context_truncation_policy: str = "reject"
    include_special_tokens: bool = False
    return_token_counts: bool = True
    seed: int | None = None


def validate_generation_config(
    config: GenerationConfig,
    *,
    scope: str,
    profile_maximum_new_tokens: int,
    profile_maximum_context_length: int,
) -> list[str]:
    errors: list[str] = []
    if config.decoding_mode not in DECODING_MODES:
        errors.append(f"decoding_mode must be one of {DECODING_MODES}")
    if config.context_truncation_policy not in CONTEXT_TRUNCATION_POLICIES:
        errors.append(f"context_truncation_policy must be one of {CONTEXT_TRUNCATION_POLICIES}")
    if config.maximum_new_tokens < 1:
        errors.append("maximum_new_tokens must be at least 1")
    if config.maximum_new_tokens > profile_maximum_new_tokens:
        errors.append("maximum_new_tokens exceeds the runtime profile limit")
    if config.minimum_new_tokens < 0:
        errors.append("minimum_new_tokens must not be negative")
    if config.minimum_new_tokens > config.maximum_new_tokens:
        errors.append("minimum_new_tokens must not exceed maximum_new_tokens")
    if config.request_timeout_seconds < 1:
        errors.append("request_timeout_seconds must be at least 1")
    if config.top_k is not None and config.top_k < 1:
        errors.append("top_k must be at least 1 when set")
    if config.temperature is not None and not (0.0 < config.temperature <= 2.0):
        errors.append("temperature must be between 0 and 2 when set")
    if scope == "public_chat":
        if config.decoding_mode != "greedy":
            errors.append("public_chat scope requires greedy decoding")
        if config.top_k is not None or config.temperature is not None:
            errors.append("public_chat scope must not enable sampling")
        if config.context_truncation_policy != "reject":
            errors.append("public_chat scope must reject over-length context, not truncate")
    return errors
