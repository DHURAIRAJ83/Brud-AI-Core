"""CPU-compatible causal self-attention."""

import math

import torch
from torch import nn

from core_model.architecture.config import BrudModelConfig
from core_model.architecture.rope import RotaryEmbedding, apply_rotary


class CausalSelfAttention(nn.Module):
    def __init__(self, config: BrudModelConfig) -> None:
        super().__init__()
        self.config = config
        self.num_heads = config.num_attention_heads
        self.head_dim = config.head_dimension
        self.q_proj = nn.Linear(config.hidden_size, config.hidden_size, bias=config.use_bias)
        self.k_proj = nn.Linear(config.hidden_size, config.hidden_size, bias=config.use_bias)
        self.v_proj = nn.Linear(config.hidden_size, config.hidden_size, bias=config.use_bias)
        self.o_proj = nn.Linear(config.hidden_size, config.hidden_size, bias=config.use_bias)
        self.attn_dropout = nn.Dropout(config.attention_dropout)
        self.resid_dropout = nn.Dropout(config.residual_dropout)
        self.rope = RotaryEmbedding(self.head_dim, config.context_length, config.rope_theta)

    def _shape(self, x: torch.Tensor) -> torch.Tensor:
        batch, seq, _ = x.shape
        return x.view(batch, seq, self.num_heads, self.head_dim).transpose(1, 2)

    def forward(
        self,
        x: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        position_ids: torch.Tensor | None = None,
    ) -> torch.Tensor:
        batch, seq, _ = x.shape
        if position_ids is None:
            position_ids = torch.arange(seq, device=x.device).unsqueeze(0).expand(batch, seq)
        query = self._shape(self.q_proj(x))
        key = self._shape(self.k_proj(x))
        value = self._shape(self.v_proj(x))
        cos, sin = self.rope(query, position_ids)
        query = apply_rotary(query, cos, sin)
        key = apply_rotary(key, cos, sin)
        scores = torch.matmul(query, key.transpose(-2, -1)) / math.sqrt(self.head_dim)
        causal = torch.triu(torch.ones(seq, seq, device=x.device, dtype=torch.bool), diagonal=1)
        scores = scores.masked_fill(causal, torch.finfo(scores.dtype).min)
        if attention_mask is not None:
            padding = attention_mask[:, None, None, :].to(dtype=torch.bool)
            scores = scores.masked_fill(~padding, torch.finfo(scores.dtype).min)
        weights = torch.softmax(scores.float(), dim=-1).to(dtype=x.dtype)
        weights = self.attn_dropout(weights)
        output = torch.matmul(weights, value).transpose(1, 2).contiguous()
        output = output.view(batch, seq, self.config.hidden_size)
        return self.resid_dropout(self.o_proj(output))
