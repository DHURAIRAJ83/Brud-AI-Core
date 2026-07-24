"""Bounded generation engine for the inference runtime.

Extends Phase 12's ``generate_greedy`` loop shape (same stop conditions:
EOS, context limit, token cap, wall-clock timeout) with cooperative
cancellation, a minimum-token floor, and mid-generation role-token
leakage detection — Phase 12's checks run only after generation
completes, but the runtime must stop immediately once a role token
leaks, per Phase 15's "do not silently present role-token leakage as a
normal answer" requirement. Post-hoc safety checks are reused unchanged
from Phase 12 (``core_model.instruction_tuning.evaluation``), never
reimplemented.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import torch

from core_model.architecture.model import BrudForCausalLM
from core_model.instruction_tuning.evaluation import (
    no_excessive_repetition,
    no_role_token_leakage,
    no_system_prompt_leakage,
    valid_unicode,
)

__all__ = [
    "run_bounded_generation",
    "no_excessive_repetition",
    "no_role_token_leakage",
    "no_system_prompt_leakage",
    "valid_unicode",
]


def _select_next_token(
    logits: torch.Tensor,
    *,
    decoding_mode: str,
    top_k: int | None,
    temperature: float | None,
    generator: torch.Generator,
    suppress_token_id: int | None,
) -> int:
    working = logits.clone()
    if suppress_token_id is not None:
        working[suppress_token_id] = float("-inf")

    if decoding_mode == "top_k_sampling" and top_k:
        scaled = working / (temperature or 1.0)
        bounded_k = min(top_k, scaled.shape[-1])
        top_values, top_indices = torch.topk(scaled, bounded_k)
        probabilities = torch.softmax(top_values, dim=-1)
        choice = torch.multinomial(probabilities, 1, generator=generator)
        return int(top_indices[choice].item())

    return int(working.argmax().item())


def run_bounded_generation(
    model: BrudForCausalLM,
    processor,
    prompt_ids: list[int],
    *,
    max_new_tokens: int,
    min_new_tokens: int,
    eos_token_id: int,
    forbidden_role_token_ids: frozenset[int],
    sequence_length: int,
    vocabulary_size: int,
    timeout_seconds: float,
    decoding_mode: str = "greedy",
    top_k: int | None = None,
    temperature: float | None = None,
    seed: int | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict[str, Any]:
    model.eval()
    if len(prompt_ids) >= sequence_length:
        return {
            "generated_text": "",
            "generated_token_ids": [],
            "stop_reason": "prompt_too_long",
            "prompt_token_count": len(prompt_ids),
            "output_token_count": 0,
        }

    generator = torch.Generator()
    if seed is not None:
        generator.manual_seed(seed)

    ids = list(prompt_ids)
    generated: list[int] = []
    started = time.perf_counter()
    stop_reason = "max_new_tokens"
    with torch.no_grad():
        for _ in range(max_new_tokens):
            if cancel_check is not None and cancel_check():
                stop_reason = "cancelled"
                break
            if time.perf_counter() - started > timeout_seconds:
                stop_reason = "timeout"
                break
            if len(ids) >= sequence_length:
                stop_reason = "context_limit"
                break

            logits = model(torch.tensor([ids], dtype=torch.long)).logits[0, -1]
            next_id = _select_next_token(
                logits,
                decoding_mode=decoding_mode,
                top_k=top_k,
                temperature=temperature,
                generator=generator,
                suppress_token_id=eos_token_id if len(generated) < min_new_tokens else None,
            )
            if next_id < 0 or next_id >= vocabulary_size:
                stop_reason = "invalid_token"
                break
            if next_id in forbidden_role_token_ids:
                stop_reason = "role_token_leakage"
                break

            ids.append(next_id)
            generated.append(next_id)
            if next_id == eos_token_id:
                stop_reason = "eos"
                break

    text = processor.decode(generated) if generated else ""
    return {
        "generated_text": text,
        "generated_token_ids": generated,
        "stop_reason": stop_reason,
        "prompt_token_count": len(prompt_ids),
        "output_token_count": len(generated),
    }
