"""Tiny bounded overfit smoke test."""

from __future__ import annotations

import time
from typing import Any

import torch

from core_model.architecture.model import BrudForCausalLM
from core_model.training.batch import pad_sequences
from core_model.training.signed_training_gate import (
    SignedTrainingAuthorizationToken,
    SignedTrainingGateEngine,
    TrainingAuthorizationError,
)


def tiny_overfit(
    model: BrudForCausalLM,
    sequence: list[int],
    *,
    pad_token_id: int,
    steps: int,
    max_steps: int,
    lr: float = 3e-3,
    signed_token: SignedTrainingAuthorizationToken | None = None,
    authorized: bool = False,
) -> dict[str, Any]:
    gate = SignedTrainingGateEngine(runtime_authorized_flag=authorized)
    gate.verify_authorization(signed_token)

    if steps < 1 or steps > max_steps:
        raise ValueError("smoke steps outside configured bounds")
    input_ids, attention_mask, labels = pad_sequences(
        [sequence],
        pad_token_id=pad_token_id,
        max_length=len(sequence),
    )
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    start = time.perf_counter()
    losses: list[float] = []
    for _ in range(steps):
        optimizer.zero_grad(set_to_none=True)
        output = model(input_ids, attention_mask=attention_mask, labels=labels)
        if output.loss is None or not torch.isfinite(output.loss):
            raise ValueError("smoke loss is not finite")
        output.loss.backward()
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=10.0)
        if not torch.isfinite(grad_norm):
            raise ValueError("smoke gradients are not finite")
        optimizer.step()
        losses.append(float(output.loss.detach()))
    return {
        "initial_loss": losses[0],
        "final_loss": losses[-1],
        "loss_reduction": losses[0] - losses[-1],
        "steps": steps,
        "passed": losses[-1] < losses[0],
        "duration_ms": int((time.perf_counter() - start) * 1000),
    }
