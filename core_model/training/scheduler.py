"""Learning-rate schedulers."""

import math

from torch.optim import Optimizer
from torch.optim.lr_scheduler import LambdaLR


def build_scheduler(optimizer: Optimizer, name: str, *, total_steps: int, warmup_steps: int):
    if name == "constant":
        return LambdaLR(optimizer, lambda _: 1.0)

    def linear(step: int) -> float:
        if warmup_steps and step < warmup_steps:
            return max(1e-8, step / warmup_steps)
        remaining = max(1, total_steps - max(step, warmup_steps))
        return max(0.0, remaining / max(1, total_steps - warmup_steps))

    if name == "linear_warmup_decay":
        return LambdaLR(optimizer, linear)
    if name == "cosine":
        return LambdaLR(
            optimizer,
            lambda step: 0.5 * (1 + math.cos(math.pi * min(step, total_steps) / total_steps)),
        )
    raise ValueError("unsupported scheduler")
