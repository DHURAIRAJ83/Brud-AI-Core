"""Validation loss evaluator."""

from __future__ import annotations

import math

import torch

from core_model.training.batch import pad_sequences


def validation_loss(
    model, blocks: list[list[int]], *, pad_token_id: int, max_batches: int
) -> dict[str, float | int | None]:
    if not blocks:
        return {"loss": None, "perplexity": None, "tokens": 0, "batches": 0}
    model.eval()
    total_loss = 0.0
    total_targets = 0
    batches = 0
    with torch.no_grad():
        for block in blocks[:max_batches]:
            ids, mask, labels = pad_sequences(
                [block], pad_token_id=pad_token_id, max_length=len(block)
            )
            output = model(ids, attention_mask=mask, labels=labels)
            targets = int((labels[:, 1:] != -100).sum().item())
            if output.loss is not None:
                total_loss += float(output.loss) * targets
                total_targets += targets
                batches += 1
    if total_targets == 0:
        return {"loss": None, "perplexity": None, "tokens": 0, "batches": batches}
    loss = total_loss / total_targets
    return {
        "loss": loss,
        "perplexity": math.exp(loss) if loss < 20 else None,
        "tokens": total_targets,
        "batches": batches,
    }
