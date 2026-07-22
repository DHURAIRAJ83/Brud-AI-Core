"""Batch utilities for bounded Phase 8 tests."""

import torch


def pad_sequences(
    sequences: list[list[int]],
    *,
    pad_token_id: int,
    max_length: int,
    truncate: bool = False,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    if not sequences:
        raise ValueError("at least one sequence is required")
    if any(not seq for seq in sequences):
        raise ValueError("empty token sequences are not allowed")
    longest = max(len(seq) for seq in sequences)
    if longest > max_length and not truncate:
        raise ValueError("sequence exceeds max_length; explicit truncation required")
    length = min(longest, max_length)
    input_ids, masks = [], []
    for seq in sequences:
        row = seq[:length]
        padding = [pad_token_id] * (length - len(row))
        input_ids.append(row + padding)
        masks.append([1] * len(row) + [0] * len(padding))
    ids = torch.tensor(input_ids, dtype=torch.long)
    attention_mask = torch.tensor(masks, dtype=torch.long)
    labels = ids.clone()
    labels[attention_mask == 0] = -100
    return ids, attention_mask, labels
