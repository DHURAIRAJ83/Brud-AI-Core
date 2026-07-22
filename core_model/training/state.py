"""Serializable trainer state."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class TrainerState:
    step: int
    processed_tokens: int
    best_validation_loss: float | None
    sampling_seed: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
