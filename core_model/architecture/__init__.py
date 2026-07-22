"""Core model architecture contracts."""

from dataclasses import dataclass
from enum import StrEnum

from core_model.architecture.config import BrudModelConfig, micro_preset, tiny_preset
from core_model.architecture.model import BrudForCausalLM, count_parameters

__all__ = [
    "BrudForCausalLM",
    "BrudModelConfig",
    "ModelConfig",
    "ModelStatus",
    "count_parameters",
    "micro_preset",
    "tiny_preset",
]


class ModelStatus(StrEnum):
    """Lifecycle states shared by future model tooling and the admin UI."""

    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"
    TRAINING = "training"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True)
class ModelConfig:
    """Will hold validated architecture and training-compatible model settings."""

    name: str = "brud-core"
    status: ModelStatus = ModelStatus.NOT_CONFIGURED

    def validate_for_training(self) -> None:
        """Validate a complete model configuration in a future phase."""

        raise NotImplementedError("Model configuration is not available in Phase 1")
