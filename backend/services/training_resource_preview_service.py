"""Phase 14 Step 12 resource preview and hard resource-bound enforcement.

Addresses Phase 13's deferred resource-bound gap (Step 36): every
executable training-strategy configuration is checked against real,
configured hard limits before a run request can even be created --
reusing the exact `Settings.pretraining_max_*` bounds
`PretrainingService._enforce_config()` already enforces for base
pretraining, plus Phase-14-specific bounds (checkpoint count, free
disk, total token budget) from `core_model.training_incremental`. An
out-of-bounds configuration is always a hard block with an explicit
reason -- never a silently clamped/corrected retry.

`PretrainingConfig` (core_model/training/pretraining_config.py) has no
epoch concept -- pretraining/instruction-tuning here are step-bounded,
not epoch-bounded -- so an optional `epochs` field is recorded as an
advisory bound only, never passed through to the underlying trainer.
"""

from __future__ import annotations

import shutil
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from core_model.training_incremental import (
    DEFAULT_MAX_CHECKPOINT_COUNT,
    DEFAULT_MAX_CONTEXT_LENGTH,
    DEFAULT_MAX_EPOCHS,
    DEFAULT_MAX_STEPS,
    DEFAULT_MAX_TOKENS,
    EXECUTION_TARGETS,
)


class TrainingResourcePreviewService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def build_preview(
        self, training_strategy: str, configuration: dict[str, Any]
    ) -> dict[str, Any]:
        blocked_reasons: list[str] = []

        batch_size = int(configuration.get("batch_size", 1))
        sequence_length = int(configuration.get("sequence_length", 64))
        total_steps = int(configuration.get("total_steps", 0))
        gradient_accumulation_steps = int(configuration.get("gradient_accumulation_steps", 1))
        epochs = int(configuration.get("epochs", 1))
        checkpoint_interval_steps = int(
            configuration.get("checkpoint_interval_steps", max(total_steps, 1))
        )
        maximum_checkpoints = int(configuration.get("maximum_checkpoints", 5))
        maximum_tokens = int(
            configuration.get("maximum_tokens", total_steps * batch_size * sequence_length)
        )

        if total_steps <= 0 or epochs <= 0:
            blocked_reasons.append(
                "total_steps and epochs must be positive -- unbounded or zero-length runs "
                "are blocked"
            )
        if batch_size > self.settings.pretraining_max_batch_size:
            blocked_reasons.append(
                f"batch_size {batch_size} exceeds configured maximum "
                f"{self.settings.pretraining_max_batch_size}"
            )
        if sequence_length > self.settings.pretraining_max_sequence_length:
            blocked_reasons.append(
                f"sequence_length {sequence_length} exceeds configured maximum "
                f"{self.settings.pretraining_max_sequence_length}"
            )
        if sequence_length > DEFAULT_MAX_CONTEXT_LENGTH:
            blocked_reasons.append(
                f"sequence_length {sequence_length} exceeds the incremental-training "
                f"context-length bound {DEFAULT_MAX_CONTEXT_LENGTH}"
            )
        if total_steps > self.settings.pretraining_max_steps:
            blocked_reasons.append(
                f"total_steps {total_steps} exceeds configured maximum "
                f"{self.settings.pretraining_max_steps}"
            )
        if total_steps > DEFAULT_MAX_STEPS:
            blocked_reasons.append(f"total_steps {total_steps} exceeds bound {DEFAULT_MAX_STEPS}")
        if gradient_accumulation_steps > self.settings.pretraining_max_gradient_accumulation:
            blocked_reasons.append("gradient_accumulation_steps exceeds configured maximum")
        if epochs > DEFAULT_MAX_EPOCHS:
            blocked_reasons.append(f"epochs {epochs} exceeds bound {DEFAULT_MAX_EPOCHS}")
        if maximum_tokens > DEFAULT_MAX_TOKENS:
            blocked_reasons.append(
                f"maximum_tokens {maximum_tokens} exceeds bound {DEFAULT_MAX_TOKENS}"
            )
        if checkpoint_interval_steps <= 0 or checkpoint_interval_steps > max(total_steps, 1):
            blocked_reasons.append(
                "checkpoint_interval_steps must be positive and within total_steps"
            )
        planned_checkpoint_count = (
            (total_steps // checkpoint_interval_steps) if checkpoint_interval_steps > 0 else 0
        )
        if (
            planned_checkpoint_count > DEFAULT_MAX_CHECKPOINT_COUNT
            or maximum_checkpoints > self.settings.pretraining_max_checkpoints
        ):
            blocked_reasons.append(
                f"planned checkpoint count exceeds bound {DEFAULT_MAX_CHECKPOINT_COUNT}"
            )

        free_bytes = shutil.disk_usage(self.settings.resolved_database_path.parent).free
        if free_bytes < self.settings.pretraining_min_free_disk_bytes:
            blocked_reasons.append(
                f"only {free_bytes} bytes free, below the required reserve "
                f"{self.settings.pretraining_min_free_disk_bytes}"
            )

        preview = {
            "training_strategy": training_strategy,
            "estimated_tokens": total_steps * batch_size * sequence_length,
            "estimated_memory_bytes": self.settings.core_max_estimated_memory_bytes,
            "planned_checkpoint_count": planned_checkpoint_count,
            "device": "cpu",
            "execution_targets_allowed": list(EXECUTION_TARGETS),
            "free_disk_bytes": free_bytes,
            "warnings": ["cpu_only_slow_execution"],
            "blocked_reasons": blocked_reasons,
            "status": "blocked" if blocked_reasons else "pass_with_warnings",
        }
        if blocked_reasons:
            raise ValidationError(
                "resource preview blocked this configuration: " + "; ".join(blocked_reasons)
            )
        return preview


__all__ = ["TrainingResourcePreviewService"]
