"""Typed model outputs."""

from dataclasses import dataclass

import torch


@dataclass(frozen=True)
class CausalLMOutput:
    logits: torch.Tensor
    loss: torch.Tensor | None
    metadata: dict[str, int]
