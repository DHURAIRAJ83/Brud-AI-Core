"""Phase 51 Sovereign Anti-Memorization & Sequence Overfitting Guard.

Tracks record-level and sequence-level exposure during training, computes effective
corpus passes (epoch equivalents), detects validation divergence, and enforces
tiered safeguards: WARN -> PAUSE -> BLOCK.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MemorizationPolicy(str, Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    PAUSE = "PAUSE"
    BLOCK = "BLOCK"


class MemorizationError(Exception):
    """Raised when an active training slice violates anti-memorization constraints."""

    pass


@dataclass
class RecordExposureState:
    record_id: str
    exposure_count: int = 0
    effective_epoch: float = 0.0
    last_seen_step: int = 0
    tokens_contributed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemorizationTelemetry:
    unique_records_tracked: int = 0
    unique_corpus_tokens: int = 0
    total_exposure_tokens: int = 0
    effective_epoch_equivalents: float = 0.0
    max_record_exposure: int = 0
    min_record_exposure: int = 0
    median_record_exposure: float = 0.0
    policy_action: str = MemorizationPolicy.ALLOW.value
    warning_count: int = 0
    pause_count: int = 0
    block_count: int = 0
    validation_divergence_observed: bool = False
    validation_gap: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Phase51MemorizationGuard:
    """Monitors training sequence repetition and halts training before severe memorization."""

    def __init__(
        self,
        unique_corpus_tokens: int,
        max_epoch_equivalents: float = 50.0,
        warn_epoch_threshold: float = 25.0,
        validation_divergence_threshold: float = 1.5,
        max_sequence_reuse: int = 100,
    ) -> None:
        self.unique_corpus_tokens = max(1, unique_corpus_tokens)
        self.max_epoch_equivalents = max_epoch_equivalents
        self.warn_epoch_threshold = warn_epoch_threshold
        self.validation_divergence_threshold = validation_divergence_threshold
        self.max_sequence_reuse = max_sequence_reuse

        self.records: dict[str, RecordExposureState] = {}
        self.total_exposure_tokens = 0
        self.current_step = 0
        self.telemetry = MemorizationTelemetry(unique_corpus_tokens=self.unique_corpus_tokens)

    def register_exposure(
        self,
        record_id: str,
        step: int,
        tokens: int,
    ) -> MemorizationPolicy:
        """Registers a training exposure event for a given record."""
        self.current_step = step
        self.total_exposure_tokens += tokens

        if record_id not in self.records:
            self.records[record_id] = RecordExposureState(
                record_id=record_id,
                exposure_count=1,
                effective_epoch=tokens / self.unique_corpus_tokens,
                last_seen_step=step,
                tokens_contributed=tokens,
            )
        else:
            state = self.records[record_id]
            state.exposure_count += 1
            state.tokens_contributed += tokens
            state.effective_epoch = state.tokens_contributed / self.unique_corpus_tokens
            state.last_seen_step = step

        return self.evaluate_policy()

    def evaluate_validation(
        self,
        train_loss: float,
        val_loss: float,
    ) -> MemorizationPolicy:
        """Checks for validation divergence indicating memorization."""
        gap = val_loss - train_loss
        self.telemetry.validation_gap = round(gap, 4)

        if gap >= self.validation_divergence_threshold and train_loss < 1.0:
            self.telemetry.validation_divergence_observed = True
            self.telemetry.block_count += 1
            self.telemetry.policy_action = MemorizationPolicy.BLOCK.value
            return MemorizationPolicy.BLOCK

        return self.evaluate_policy()

    def evaluate_policy(self) -> MemorizationPolicy:
        """Evaluates exposure ratios against configured safety thresholds."""
        epoch_equivalents = self.total_exposure_tokens / self.unique_corpus_tokens
        self.telemetry.effective_epoch_equivalents = round(epoch_equivalents, 2)
        self.telemetry.total_exposure_tokens = self.total_exposure_tokens
        self.telemetry.unique_records_tracked = len(self.records)

        counts = [s.exposure_count for s in self.records.values()] or [0]
        self.telemetry.max_record_exposure = max(counts)
        self.telemetry.min_record_exposure = min(counts)
        sorted_counts = sorted(counts)
        self.telemetry.median_record_exposure = float(sorted_counts[len(sorted_counts) // 2])

        # Priority 1: BLOCK
        if epoch_equivalents >= self.max_epoch_equivalents or self.telemetry.max_record_exposure >= self.max_sequence_reuse:
            self.telemetry.policy_action = MemorizationPolicy.BLOCK.value
            self.telemetry.block_count += 1
            return MemorizationPolicy.BLOCK

        # Priority 2: PAUSE
        if epoch_equivalents >= (self.max_epoch_equivalents * 0.90):
            self.telemetry.policy_action = MemorizationPolicy.PAUSE.value
            self.telemetry.pause_count += 1
            return MemorizationPolicy.PAUSE

        # Priority 3: WARN
        if epoch_equivalents >= self.warn_epoch_threshold:
            self.telemetry.policy_action = MemorizationPolicy.WARN.value
            self.telemetry.warning_count += 1
            return MemorizationPolicy.WARN

        self.telemetry.policy_action = MemorizationPolicy.ALLOW.value
        return MemorizationPolicy.ALLOW
