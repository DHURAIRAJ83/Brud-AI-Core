"""Bounded pretraining configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PretrainingConfig:
    batch_size: int = 1
    gradient_accumulation_steps: int = 2
    sequence_length: int = 64
    total_steps: int = 20
    maximum_tokens: int = 100_000
    learning_rate: float = 3e-4
    minimum_learning_rate: float = 1e-5
    warmup_steps: int = 0
    weight_decay: float = 0.01
    beta1: float = 0.9
    beta2: float = 0.95
    epsilon: float = 1e-8
    gradient_clip_norm: float = 1.0
    checkpoint_interval_steps: int = 10
    validation_interval_steps: int = 10
    metric_interval_steps: int = 1
    maximum_checkpoints: int = 5
    initialization_seed: int = 42
    sampling_seed: int = 42
    optimizer: str = "adamw"
    scheduler: str = "constant"
    device: str = "cpu"
    dtype: str = "float32"
    dataloader_workers: int = 0
    shuffle: bool = False
    overlength_policy: str = "split_oversized"
    eos_policy: str = "append_eos"

    def validate(self) -> None:
        if self.batch_size < 1 or self.gradient_accumulation_steps < 1:
            raise ValueError("batch size and gradient accumulation must be positive")
        if self.sequence_length < 2 or self.total_steps < 1:
            raise ValueError("sequence length and total steps must be positive")
        if self.optimizer != "adamw":
            raise ValueError("Phase 9 supports only adamw")
        if self.scheduler not in {"constant", "linear_warmup_decay", "cosine"}:
            raise ValueError("unsupported scheduler")
        if self.device != "cpu" or self.dtype != "float32" or self.dataloader_workers != 0:
            raise ValueError("Phase 9 supports cpu, float32, and zero dataloader workers")
        if self.overlength_policy not in {"drop_oversized", "split_oversized"}:
            raise ValueError("unsupported overlength policy")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def from_mapping(raw: dict[str, object]) -> PretrainingConfig:
    data = {
        key: value for key, value in raw.items() if key in PretrainingConfig.__dataclass_fields__
    }
    config = PretrainingConfig(**data)
    config.validate()
    return config
