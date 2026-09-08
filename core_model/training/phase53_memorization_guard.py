"""Phase 53 Anti-Memorization Guard V3.

Enforces fail-closed multi-dimensional memorization defense, tracking sequence exposure,
n-gram repetition, dominant record concentration, validation divergence, source/domain concentration,
and effective epochs.
"""

from __future__ import annotations

from collections import Counter
from enum import Enum
import hashlib
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field


class GuardAction(str, Enum):
    """Guard state policy transitions."""

    ALLOW = "ALLOW"
    WARN = "WARN"
    PAUSE = "PAUSE"
    BLOCK = "BLOCK"


class RecordExposure(BaseModel):
    """Tracks exposure history for a specific sequence record."""

    record_id: str
    sequence_hash: str
    domain: str = "general"
    source_id: str = "unknown"
    exposure_count: int = 0
    effective_epoch: float = 0.0
    last_seen_step: int = 0


class Phase53MemorizationGuard:
    """V3 Anti-Memorization Guard enforcing strict mathematical fail-closed boundaries."""

    def __init__(
        self,
        unique_corpus_tokens: int = 2906,
        warn_epoch_threshold: float = 10.0,
        pause_epoch_threshold: float = 15.0,
        block_epoch_threshold: float = 25.0,
        concentration_threshold: float = 0.40,
        divergence_threshold: float = 0.25,
        repetition_threshold: float = 0.30,
    ):
        self.unique_corpus_tokens = max(1, unique_corpus_tokens)
        self.warn_epoch_threshold = warn_epoch_threshold
        self.pause_epoch_threshold = pause_epoch_threshold
        self.block_epoch_threshold = block_epoch_threshold
        self.concentration_threshold = concentration_threshold
        self.divergence_threshold = divergence_threshold
        self.repetition_threshold = repetition_threshold

        self.exposures: Dict[str, RecordExposure] = {}
        self.current_state: GuardAction = GuardAction.ALLOW
        self.state_history: List[Dict[str, Any]] = []

        self.total_tokens_seen: int = 0
        self.total_steps_seen: int = 0
        self.last_train_loss: Optional[float] = None
        self.last_val_loss: Optional[float] = None
        self.ngram_seen: Counter = Counter()

    def record_step_exposure(
        self,
        step: int,
        batch_records: List[Dict[str, Any]],
        tokens_in_batch: int,
        train_loss: Optional[float] = None,
        val_loss: Optional[float] = None,
    ) -> GuardAction:
        """Records exposure of a batch of records and updates guard state."""
        self.total_steps_seen = step
        self.total_tokens_seen += tokens_in_batch
        if train_loss is not None:
            self.last_train_loss = train_loss
        if val_loss is not None:
            self.last_val_loss = val_loss

        # Track per-record exposure
        for item in batch_records:
            rec_id = item.get("record_id") or hashlib.sha256(item.get("text", "").encode("utf-8")).hexdigest()[:12]
            text = item.get("text", "")
            seq_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            domain = item.get("domain", "general")
            src = item.get("source_id", "unknown")

            if rec_id not in self.exposures:
                self.exposures[rec_id] = RecordExposure(
                    record_id=rec_id,
                    sequence_hash=seq_hash,
                    domain=domain,
                    source_id=src,
                )

            rec = self.exposures[rec_id]
            rec.exposure_count += 1
            rec.effective_epoch = self.total_tokens_seen / self.unique_corpus_tokens
            rec.last_seen_step = step

            # Track 3-grams for sequence repetition
            words = text.split()
            for i in range(len(words) - 2):
                tri = " ".join(words[i : i + 3])
                self.ngram_seen[tri] += 1

        # Evaluate transitions
        new_state = self._evaluate_policy()
        if new_state != self.current_state:
            self.state_history.append(
                {
                    "step": step,
                    "previous_state": self.current_state.value,
                    "new_state": new_state.value,
                    "effective_epoch": round(self.get_effective_epochs(), 4),
                    "dominant_concentration": round(self.get_dominant_concentration(), 4),
                    "validation_divergence": round(self.get_validation_divergence(), 4),
                }
            )
            self.current_state = new_state

        return self.current_state

    def get_effective_epochs(self) -> float:
        return self.total_tokens_seen / self.unique_corpus_tokens

    def get_dominant_concentration(self) -> float:
        """Returns the exposure share of the top 10% most exposed records (meaningful when >= 10 records tracked)."""
        if len(self.exposures) < 10:
            return 0.0
        counts = sorted([r.exposure_count for r in self.exposures.values()], reverse=True)
        top_k = max(1, int(round(len(counts) * 0.10)))
        top_sum = sum(counts[:top_k])
        total_sum = sum(counts)
        return top_sum / max(1, total_sum)

    def get_validation_divergence(self) -> float:
        """Returns validation gap: max(0.0, val_loss - train_loss)."""
        if self.last_train_loss is not None and self.last_val_loss is not None:
            return max(0.0, self.last_val_loss - self.last_train_loss)
        return 0.0

    def get_repetition_ratio(self) -> float:
        """Ratio of repeated trigrams to total observed trigrams."""
        if not self.ngram_seen:
            return 0.0
        total = sum(self.ngram_seen.values())
        repeated = sum(cnt for cnt in self.ngram_seen.values() if cnt > 1)
        return repeated / max(1, total)

    def _evaluate_policy(self) -> GuardAction:
        """Evaluates thresholds to determine fail-closed state."""
        effective_epochs = self.get_effective_epochs()
        dominant_conc = self.get_dominant_concentration()
        val_gap = self.get_validation_divergence()
        rep_ratio = self.get_repetition_ratio()

        # BLOCK conditions: integrity or catastrophic repetition
        if effective_epochs >= self.block_epoch_threshold:
            return GuardAction.BLOCK
        if rep_ratio > 0.85:
            return GuardAction.BLOCK

        # PAUSE conditions: dominant concentration or divergence
        if dominant_conc > self.concentration_threshold:
            return GuardAction.PAUSE
        if val_gap > self.divergence_threshold:
            return GuardAction.PAUSE
        if effective_epochs >= self.pause_epoch_threshold:
            return GuardAction.PAUSE

        # WARN conditions: epoch threshold or early concentration
        if effective_epochs >= self.warn_epoch_threshold:
            return GuardAction.WARN
        if dominant_conc > 0.30:
            return GuardAction.WARN

        return GuardAction.ALLOW

    def should_halt(self) -> bool:
        """Returns True if training MUST halt immediately."""
        return self.current_state in {GuardAction.PAUSE, GuardAction.BLOCK}

    def get_status_summary(self) -> Dict[str, Any]:
        return {
            "current_state": self.current_state.value,
            "total_tokens_seen": self.total_tokens_seen,
            "effective_epochs": round(self.get_effective_epochs(), 4),
            "dominant_concentration": round(self.get_dominant_concentration(), 4),
            "validation_divergence": round(self.get_validation_divergence(), 4),
            "repetition_ratio": round(self.get_repetition_ratio(), 4),
            "unique_records_tracked": len(self.exposures),
            "transition_count": len(self.state_history),
        }
