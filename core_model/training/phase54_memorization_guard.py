"""Phase 54 Anti-Memorization & Data Overfitting Guard Engine V4.

Enhanced multi-dimensional exposure tracking:
1. Record-Level Exposure & Dominant Record Concentration
2. Source-Level Exposure & Source Concentration
3. Domain-Level Exposure & Domain Concentration
4. Sequence-Level Repetition Ratio & N-Gram Looping Penalty
5. Effective Epoch Tracking (Cumulative Tokens / 3,918 Unique Tokens)
6. Validation Divergence Gap (Validation Loss - Training Loss)
7. Fail-Closed Guard Actions: ALLOW, WARN, PAUSE, BLOCK
"""

from __future__ import annotations

import collections
import enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class GuardAction(str, enum.Enum):
    ALLOW = "ALLOW"
    WARN = "WARN"
    PAUSE = "PAUSE"
    BLOCK = "BLOCK"


@dataclass
class RecordExposureTelemetry:
    record_id: str
    exposure_count: int = 0
    total_tokens_exposed: int = 0
    first_seen_step: int = 0
    last_seen_step: int = 0
    domain: str = "general"
    source_id: str = "unknown"


class Phase54MemorizationGuard:
    def __init__(
        self,
        unique_corpus_tokens: int = 3918,
        warn_epoch_threshold: float = 10.0,
        pause_epoch_threshold: float = 15.0,
        block_epoch_threshold: float = 25.0,
        concentration_threshold: float = 0.40,
        domain_concentration_threshold: float = 0.50,
        divergence_threshold: float = 0.25,
        repetition_threshold: float = 0.50,
        window_size: int = 100,
    ):
        self.unique_corpus_tokens = max(1, unique_corpus_tokens)
        self.warn_epoch_threshold = warn_epoch_threshold
        self.pause_epoch_threshold = pause_epoch_threshold
        self.block_epoch_threshold = block_epoch_threshold
        self.concentration_threshold = concentration_threshold
        self.domain_concentration_threshold = domain_concentration_threshold
        self.divergence_threshold = divergence_threshold
        self.repetition_threshold = repetition_threshold
        self.window_size = window_size

        self.exposures: Dict[str, RecordExposureTelemetry] = {}
        self.domain_exposures: Dict[str, int] = collections.defaultdict(int)
        self.source_exposures: Dict[str, int] = collections.defaultdict(int)

        self.sequence_window: collections.deque[str] = collections.deque(maxlen=window_size)
        self.total_tokens_seen: int = 0
        self.current_step: int = 0
        self.last_train_loss: Optional[float] = None
        self.last_val_loss: Optional[float] = None
        self.current_state: GuardAction = GuardAction.ALLOW
        self.state_history: List[Dict[str, Any]] = []

    def record_step_exposure(
        self,
        step: int,
        batch_records: List[Dict[str, Any]],
        tokens_in_batch: int,
        train_loss: Optional[float] = None,
        val_loss: Optional[float] = None,
    ) -> GuardAction:
        """Records exposure telemetry for records, domains, sources, and evaluates policy."""
        self.current_step = step
        self.total_tokens_seen += tokens_in_batch
        self.last_train_loss = train_loss
        self.last_val_loss = val_loss

        tokens_per_rec = max(1, tokens_in_batch // max(1, len(batch_records)))

        for r in batch_records:
            rid = r.get("record_id", "unknown")
            text = r.get("text", "")
            domain = r.get("domain", "general")
            source_id = r.get("source_id", "unknown")

            if rid not in self.exposures:
                self.exposures[rid] = RecordExposureTelemetry(
                    record_id=rid,
                    first_seen_step=step,
                    domain=domain,
                    source_id=source_id,
                )

            tele = self.exposures[rid]
            tele.exposure_count += 1
            tele.total_tokens_exposed += tokens_per_rec
            tele.last_seen_step = step

            self.domain_exposures[domain] += tokens_per_rec
            self.source_exposures[source_id] += tokens_per_rec

            if text:
                prefix = text[:64]
                self.sequence_window.append(prefix)

        action = self._evaluate_policy()
        if action != self.current_state:
            self.state_history.append({
                "step": step,
                "previous_state": self.current_state.value,
                "new_state": action.value,
                "effective_epochs": self.get_effective_epochs(),
                "concentration": self.get_dominant_concentration(),
                "domain_concentration": self.get_domain_concentration(),
                "divergence": self.get_validation_divergence(),
            })
            self.current_state = action

        return action

    def get_effective_epochs(self) -> float:
        return self.total_tokens_seen / self.unique_corpus_tokens

    def get_dominant_concentration(self) -> float:
        """Share of total exposures taken by the top 10% most exposed records."""
        if len(self.exposures) < 10:
            return 0.0
        counts = sorted([r.exposure_count for r in self.exposures.values()], reverse=True)
        top_k = max(1, int(round(len(counts) * 0.10)))
        top_sum = sum(counts[:top_k])
        total_sum = sum(counts)
        return top_sum / max(1, total_sum)

    def get_domain_concentration(self) -> float:
        """Share of total exposures represented by the single largest domain."""
        if not self.domain_exposures:
            return 0.0
        max_dom = max(self.domain_exposures.values())
        total_dom = sum(self.domain_exposures.values())
        return max_dom / max(1, total_dom)

    def get_source_concentration(self) -> float:
        """Share of total exposures represented by the single largest source."""
        if not self.source_exposures:
            return 0.0
        max_src = max(self.source_exposures.values())
        total_src = sum(self.source_exposures.values())
        return max_src / max(1, total_src)

    def get_validation_divergence(self) -> float:
        if self.last_train_loss is not None and self.last_val_loss is not None:
            return max(0.0, self.last_val_loss - self.last_train_loss)
        return 0.0

    def get_repetition_ratio(self) -> float:
        if len(self.sequence_window) < 10:
            return 0.0
        total = len(self.sequence_window)
        unique = len(set(self.sequence_window))
        return (total - unique) / total

    def _evaluate_policy(self) -> GuardAction:
        epochs = self.get_effective_epochs()
        dominant_conc = self.get_dominant_concentration()
        domain_conc = self.get_domain_concentration()
        divergence = self.get_validation_divergence()
        repetition = self.get_repetition_ratio()

        # Hard BLOCK condition
        if epochs >= self.block_epoch_threshold:
            return GuardAction.BLOCK

        # Fail-closed PAUSE conditions
        if epochs >= self.pause_epoch_threshold:
            return GuardAction.PAUSE
        if dominant_conc >= self.concentration_threshold:
            return GuardAction.PAUSE
        if domain_conc >= self.domain_concentration_threshold and len(self.domain_exposures) >= 3:
            return GuardAction.PAUSE
        if divergence >= self.divergence_threshold:
            return GuardAction.PAUSE
        if repetition >= self.repetition_threshold:
            return GuardAction.PAUSE

        # Soft WARN conditions
        if epochs >= self.warn_epoch_threshold or dominant_conc >= (self.concentration_threshold * 0.85):
            return GuardAction.WARN

        return GuardAction.ALLOW

    def should_halt(self) -> bool:
        return self.current_state in (GuardAction.PAUSE, GuardAction.BLOCK)

    def get_status_summary(self) -> Dict[str, Any]:
        return {
            "current_state": self.current_state.value,
            "total_tokens_seen": self.total_tokens_seen,
            "effective_epochs": round(self.get_effective_epochs(), 2),
            "dominant_concentration": round(self.get_dominant_concentration(), 4),
            "domain_concentration": round(self.get_domain_concentration(), 4),
            "source_concentration": round(self.get_source_concentration(), 4),
            "validation_divergence": round(self.get_validation_divergence(), 4),
            "repetition_ratio": round(self.get_repetition_ratio(), 4),
            "tracked_records": len(self.exposures),
            "tracked_domains": len(self.domain_exposures),
            "tracked_sources": len(self.source_exposures),
        }
