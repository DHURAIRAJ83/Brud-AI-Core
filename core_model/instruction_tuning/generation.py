"""Bounded, admin-only greedy diagnostic generation.

No sampling, no temperature, no KV-cache — a small deterministic loop that
stops at EOS, the model's context limit, a hard token cap, or a wall-clock
timeout. This is evaluation evidence only; it is never called from any
public-facing route and never persists a conversation.
"""

from __future__ import annotations

import time
from typing import Any

import torch

from core_model.architecture.model import BrudForCausalLM


def generate_greedy(
    model: BrudForCausalLM,
    processor,
    prompt_text: str,
    *,
    max_new_tokens: int,
    eos_token_id: int,
    sequence_length: int,
    vocabulary_size: int,
    timeout_seconds: float = 5.0,
) -> dict[str, Any]:
    model.eval()
    prompt_ids = processor.encode(prompt_text, out_type=int)
    if len(prompt_ids) >= sequence_length:
        return {
            "generated_text": "",
            "generated_token_ids": [],
            "stopped_reason": "prompt_too_long",
            "prompt_token_count": len(prompt_ids),
            "output_token_count": 0,
        }

    ids = list(prompt_ids)
    generated: list[int] = []
    started = time.perf_counter()
    stopped_reason = "max_new_tokens"
    with torch.no_grad():
        for _ in range(max_new_tokens):
            if time.perf_counter() - started > timeout_seconds:
                stopped_reason = "timeout"
                break
            if len(ids) >= sequence_length:
                stopped_reason = "context_limit"
                break
            output = model(torch.tensor([ids], dtype=torch.long))
            next_id = int(output.logits[0, -1].argmax().item())
            if next_id < 0 or next_id >= vocabulary_size:
                stopped_reason = "invalid_token"
                break
            ids.append(next_id)
            generated.append(next_id)
            if next_id == eos_token_id:
                stopped_reason = "eos"
                break

    text = processor.decode(generated) if generated else ""
    return {
        "generated_text": text,
        "generated_token_ids": generated,
        "stopped_reason": stopped_reason,
        "prompt_token_count": len(prompt_ids),
        "output_token_count": len(generated),
    }
