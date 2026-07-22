"""SwiGLU feed-forward block."""

import torch
from torch import nn
from torch.nn import functional as F

from core_model.architecture.config import BrudModelConfig


class SwiGLUFeedForward(nn.Module):
    def __init__(self, config: BrudModelConfig) -> None:
        super().__init__()
        self.gate_proj = nn.Linear(config.hidden_size, config.intermediate_size, bias=config.use_bias)
        self.up_proj = nn.Linear(config.hidden_size, config.intermediate_size, bias=config.use_bias)
        self.down_proj = nn.Linear(config.intermediate_size, config.hidden_size, bias=config.use_bias)
        self.dropout = nn.Dropout(config.residual_dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.down_proj(F.silu(self.gate_proj(x)) * self.up_proj(x)))
