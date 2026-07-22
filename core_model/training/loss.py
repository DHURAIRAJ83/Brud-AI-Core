"""Causal language-model loss utilities."""

import torch
from torch.nn import functional as F


def causal_lm_loss(logits: torch.Tensor, labels: torch.Tensor, ignore_index: int = -100) -> torch.Tensor:
    if logits.ndim != 3 or labels.ndim != 2:
        raise ValueError("logits must be [B,S,V] and labels must be [B,S]")
    if logits.shape[:2] != labels.shape:
        raise ValueError("logits and labels shape mismatch")
    shift_logits = logits[:, :-1, :].contiguous()
    shift_labels = labels[:, 1:].contiguous()
    if not torch.any(shift_labels != ignore_index):
        raise ValueError("causal LM loss requires at least one valid target token")
    return F.cross_entropy(
        shift_logits.view(-1, shift_logits.size(-1)),
        shift_labels.view(-1),
        ignore_index=ignore_index,
    )
