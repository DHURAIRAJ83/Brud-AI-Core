"""Deterministic per-language loss evaluation for Phase 11 base training."""

from __future__ import annotations

from typing import Any

import torch

from core_model.training.batch import pad_sequences
from core_model.training.diagnostics import safe_perplexity


def evaluate_language_texts(
    model,
    processor,
    texts: list[str],
    *,
    pad_token_id: int,
    eos_token_id: int,
    sequence_length: int,
    vocabulary_size: int,
) -> dict[str, Any]:
    """Evaluate loss/perplexity/coverage for one language's held-out texts.

    Each text is encoded independently and evaluated as its own bounded
    block; texts longer than ``sequence_length`` are truncated (counted in
    ``long_sequence_rate``), never silently dropped.
    """

    if not texts:
        return {
            "evaluated_records": 0,
            "evaluated_tokens": 0,
            "loss": None,
            "perplexity": None,
            "unknown_token_rate": 0.0,
            "average_tokens_per_record": 0.0,
            "maximum_tokens_per_record": 0,
            "long_sequence_rate": 0.0,
        }
    model.eval()
    unk_id = processor.unk_id() if hasattr(processor, "unk_id") else -1
    lengths: list[int] = []
    total_loss = 0.0
    total_targets = 0
    total_unknowns = 0
    total_tokens_all = 0
    long_sequences = 0
    with torch.no_grad():
        for text in texts:
            ids = processor.encode(text, out_type=int)
            if eos_token_id >= 0:
                ids = [*ids, eos_token_id]
            if not ids:
                continue
            total_unknowns += sum(1 for token_id in ids if token_id == unk_id)
            total_tokens_all += len(ids)
            lengths.append(len(ids))
            if len(ids) > sequence_length:
                long_sequences += 1
            block = ids[:sequence_length]
            safe_block = [
                token_id if 0 <= token_id < vocabulary_size else pad_token_id for token_id in block
            ]
            model_ids, mask, labels = pad_sequences(
                [safe_block], pad_token_id=pad_token_id, max_length=sequence_length, truncate=True
            )
            output = model(model_ids, attention_mask=mask, labels=labels)
            targets = int((labels[:, 1:] != -100).sum().item())
            if output.loss is not None and targets:
                total_loss += float(output.loss) * targets
                total_targets += targets
    loss = (total_loss / total_targets) if total_targets else None
    return {
        "evaluated_records": len(lengths),
        "evaluated_tokens": total_tokens_all,
        "loss": loss,
        "perplexity": safe_perplexity(loss) if loss is not None else None,
        "unknown_token_rate": (total_unknowns / total_tokens_all) if total_tokens_all else 0.0,
        "average_tokens_per_record": (total_tokens_all / len(lengths)) if lengths else 0.0,
        "maximum_tokens_per_record": max(lengths) if lengths else 0,
        "long_sequence_rate": (long_sequences / len(lengths)) if lengths else 0.0,
    }
