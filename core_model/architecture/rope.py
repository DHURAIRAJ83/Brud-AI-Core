"""Rotary positional embeddings."""

import torch
from torch import nn


class RotaryEmbedding(nn.Module):
    def __init__(self, dim: int, max_position: int, theta: float = 10000.0) -> None:
        super().__init__()
        if dim % 2:
            raise ValueError("RoPE dimension must be even")
        inv_freq = 1.0 / (theta ** (torch.arange(0, dim, 2).float() / dim))
        positions = torch.arange(max_position, dtype=torch.float32)
        freqs = torch.outer(positions, inv_freq)
        self.register_buffer("cos_cached", freqs.cos(), persistent=False)
        self.register_buffer("sin_cached", freqs.sin(), persistent=False)

    def forward(self, x: torch.Tensor, position_ids: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        cos = self.cos_cached[position_ids].to(device=x.device, dtype=x.dtype)
        sin = self.sin_cached[position_ids].to(device=x.device, dtype=x.dtype)
        return cos.unsqueeze(1), sin.unsqueeze(1)


def rotate_half(x: torch.Tensor) -> torch.Tensor:
    x1 = x[..., ::2]
    x2 = x[..., 1::2]
    return torch.stack((-x2, x1), dim=-1).flatten(-2)


def apply_rotary(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> torch.Tensor:
    cos = torch.repeat_interleave(cos, 2, dim=-1)
    sin = torch.repeat_interleave(sin, 2, dim=-1)
    return (x * cos) + (rotate_half(x) * sin)
