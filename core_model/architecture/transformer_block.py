"""Transformer block."""

import torch
from torch import nn

from core_model.architecture.attention import CausalSelfAttention
from core_model.architecture.config import BrudModelConfig
from core_model.architecture.feed_forward import SwiGLUFeedForward


class RMSNorm(nn.Module):
    def __init__(self, hidden_size: int, eps: float = 1e-6) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.ones(hidden_size))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        variance = x.float().pow(2).mean(dim=-1, keepdim=True)
        normalized = x * torch.rsqrt(variance.to(dtype=x.dtype) + self.eps)
        return normalized * self.weight


class TransformerBlock(nn.Module):
    def __init__(self, config: BrudModelConfig) -> None:
        super().__init__()
        self.input_norm = RMSNorm(config.hidden_size, config.rms_norm_epsilon)
        self.attention = CausalSelfAttention(config)
        self.post_attention_norm = RMSNorm(config.hidden_size, config.rms_norm_epsilon)
        self.feed_forward = SwiGLUFeedForward(config)

    def forward(
        self,
        x: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        position_ids: torch.Tensor | None = None,
    ) -> torch.Tensor:
        x = x + self.attention(self.input_norm(x), attention_mask, position_ids)
        return x + self.feed_forward(self.post_attention_norm(x))
