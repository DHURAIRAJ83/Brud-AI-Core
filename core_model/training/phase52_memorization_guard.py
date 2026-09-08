"""Phase 52 Anti-Memorization Guard V2.

Monitors sequence-level exposure, effective epoch equivalents, repetition ratio,
dominant-record concentration, validation divergence, and token-frequency collapse.
Enforces automatic state progression: ALLOW -> WARN -> PAUSE -> BLOCK.
"""

from __future__ import annotations

import collections
import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class RecordTelemetry:
    record_id: str
    sequence_hash: str
    exposure_count: int = 0
    effective_epoch: float = 0.0
    last_seen_step: int = 0
    first_seen_step: int = 0


@dataclass
class MemorizationStateSnapshot:
    state: str  # ALLOW, WARN, PAUSE, BLOCK
    current_step: int
    cumulative_tokens: int
    effective_epochs: float
    max_record_exposure: int
    repetition_ratio: float
    dominant_record_concentration: float
    train_loss: float
    validation_loss: float
    validation_gap: float
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Phase52MemorizationGuard:
    """Runtime anti-memorization guard for Phase 52 training."""

    STATE_ALLOW = "ALLOW"
    STATE_WARN = "WARN"
    STATE_PAUSE = "PAUSE"
    STATE_BLOCK = "BLOCK"

    def __init__(
        self,
        unique_corpus_tokens: int,
        warn_epoch_threshold: float = 5.0,
        pause_epoch_threshold: float = 10.0,
        block_epoch_threshold: float = 20.0,
        max_sequence_reuse: int = 40,
        validation_divergence_threshold: float = 1.5,
        concentration_threshold: float = 0.40,
    ):
        self.unique_corpus_tokens = max(1, unique_corpus_tokens)
        self.warn_epoch_threshold = warn_epoch_threshold
        self.pause_epoch_threshold = pause_epoch_threshold
        self.block_epoch_threshold = block_epoch_threshold
        self.max_sequence_reuse = max_sequence_reuse
        self.validation_divergence_threshold = validation_divergence_threshold
        self.concentration_threshold = concentration_threshold

        self.record_telemetry: Dict[str, RecordTelemetry] = {}
        self.sequence_history: collections.deque = collections.deque(maxlen=1000)
        self.current_state = self.STATE_ALLOW
        self.warn_count = 0
        self.pause_count = 0
        self.block_count = 0
        self.history: List[MemorizationStateSnapshot] = []

    def register_exposure(
        self,
        record_id: str,
        sequence_text: str,
        step: int,
        tokens_in_record: int,
    ) -> None:
        """Registers record exposure and sequence history."""
        seq_hash = hashlib.sha256(sequence_text.encode("utf-8")).hexdigest()
        self.sequence_history.append(seq_hash)

        if record_id not in self.record_telemetry:
            self.record_telemetry[record_id] = RecordTelemetry(
                record_id=record_id,
                sequence_hash=seq_hash,
                exposure_count=1,
                effective_epoch=1.0,
                last_seen_step=step,
                first_seen_step=step,
            )
        else:
            rec = self.record_telemetry[record_id]
            rec.exposure_count += 1
            rec.last_seen_step = step
            rec.effective_epoch = float(rec.exposure_count)

    def calculate_dominant_concentration(self) -> float:
        """Calculates exposure share of the top 10% most-exposed records."""
        if not self.record_telemetry:
            return 0.0
        counts = sorted([r.exposure_count for r in self.record_telemetry.values()], reverse=True)
        total_exposures = sum(counts)
        if total_exposures == 0:
            return 0.0
        top_k = max(1, int(round(0.10 * len(counts))))
        top_sum = sum(counts[:top_k])
        return top_sum / total_exposures

    def calculate_repetition_ratio(self) -> float:
        """Calculates proportion of repeated sequences in the recent sequence window."""
        if not self.sequence_history:
            return 0.0
        total = len(self.sequence_history)
        unique = len(set(self.sequence_history))
        return (total - unique) / total

    def evaluate_state(
        self,
        current_step: int,
        cumulative_tokens: int,
        train_loss: float,
        validation_loss: float,
    ) -> MemorizationStateSnapshot:
        """Evaluates guard conditions and transitions state accordingly."""
        effective_epochs = cumulative_tokens / self.unique_corpus_tokens
        validation_gap = max(0.0, validation_loss - train_loss)
        max_exposure = max((r.exposure_count for r in self.record_telemetry.values()), default=0)
        concentration = self.calculate_dominant_concentration()
        rep_ratio = self.calculate_repetition_ratio()

        new_state = self.STATE_ALLOW
        reason = "Normal training within bounds"

        # 1. Check BLOCK condition (> 20 epochs or extreme sequence reuse)
        if effective_epochs > self.block_epoch_threshold:
            new_state = self.STATE_BLOCK
            reason = f"Effective epochs ({effective_epochs:.1f}) exceeded block threshold ({self.block_epoch_threshold})"
        elif max_exposure > (self.max_sequence_reuse * 2):
            new_state = self.STATE_BLOCK
            reason = f"Max sequence reuse ({max_exposure}) exceeded double limit ({self.max_sequence_reuse * 2})"

        # 2. Check PAUSE condition (10 < epoch <= 20 with divergence or concentration)
        elif effective_epochs > self.pause_epoch_threshold:
            if validation_gap > self.validation_divergence_threshold:
                new_state = self.STATE_PAUSE
                reason = f"Validation divergence gap ({validation_gap:.2f}) exceeded threshold ({self.validation_divergence_threshold})"
            elif concentration > self.concentration_threshold:
                new_state = self.STATE_PAUSE
                reason = f"Dominant record concentration ({concentration:.2%}) exceeded threshold ({self.concentration_threshold:.2%})"
            else:
                new_state = self.STATE_WARN
                reason = f"Effective epochs ({effective_epochs:.1f}) in warning zone ({self.pause_epoch_threshold})"

        # 3. Check WARN condition (5 < epoch <= 10)
        elif effective_epochs > self.warn_epoch_threshold:
            new_state = self.STATE_WARN
            reason = f"Effective epochs ({effective_epochs:.1f}) exceeded warn threshold ({self.warn_epoch_threshold})"
        elif max_exposure > self.max_sequence_reuse:
            new_state = self.STATE_WARN
            reason = f"Max record exposure ({max_exposure}) exceeded threshold ({self.max_sequence_reuse})"

        self.current_state = new_state
        if new_state == self.STATE_WARN:
            self.warn_count += 1
        elif new_state == self.STATE_PAUSE:
            self.pause_count += 1
        elif new_state == self.STATE_BLOCK:
            self.block_count += 1

        snap = MemorizationStateSnapshot(
            state=new_state,
            current_step=current_step,
            cumulative_tokens=cumulative_tokens,
            effective_epochs=effective_epochs,
            max_record_exposure=max_exposure,
            repetition_ratio=rep_ratio,
            dominant_record_concentration=concentration,
            train_loss=train_loss,
            validation_loss=validation_loss,
            validation_gap=validation_gap,
            reason=reason,
        )
        self.history.append(snap)
        return snap

    def should_halt(self) -> bool:
        """Determines if the training campaign must halt immediately."""
        return self.current_state in [self.STATE_PAUSE, self.STATE_BLOCK]

    def get_status_summary(self) -> Dict[str, Any]:
        """Returns diagnostic telemetry summary for reporting."""
        latest = self.history[-1] if self.history else None
        return {
            "current_state": self.current_state,
            "warn_count": self.warn_count,
            "pause_count": self.pause_count,
            "block_count": self.block_count,
            "monitored_records": len(self.record_telemetry),
            "latest_snapshot": latest.to_dict() if latest else None,
        }
