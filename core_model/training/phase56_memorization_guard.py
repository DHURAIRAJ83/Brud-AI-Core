"""Phase 56 Anti-Memorization Guard V5.

Extended from Phase 54 guard architecture with Phase 55 corpus token count (12,277 train tokens).

Tracks:
1. Effective epochs (cumulative exposure / 12,277 unique train tokens)
2. Cumulative exposure tokens
3. Record exposure frequency & dominant record concentration
4. Source concentration
5. Domain concentration
6. N-gram / sequence window repetition ratio
7. Output generation repetition
8. Train/validation loss divergence
9. Capability score (set externally at evaluation milestones)
10. Seen/held-out/OOD gap

Fail-Closed Guard Actions:
  ALLOW  -> Training may proceed
  WARN   -> Soft warning logged; training continues with alerting
  PAUSE  -> Training must pause until human review
  BLOCK  -> Training must stop immediately; cannot continue

Epoch thresholds:
  WARN  >= 10 effective epochs
  PAUSE >= 15 effective epochs
  BLOCK >= 25 effective epochs
"""

from __future__ import annotations

import collections
import enum
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


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


@dataclass
class CapabilityMilestone:
    milestone_id: str
    step: int
    effective_epochs: float
    score: float
    seen_score: float
    held_out_score: float
    ood_score: float
    train_loss: Optional[float]
    val_loss: Optional[float]
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


class Phase56MemorizationGuard:
    """Phase 56 Anti-Memorization Guard V5.

    Unique corpus tokens = 12,277 (Phase 55 train split).
    All thresholds are fail-closed: when triggered, training halts.
    """

    # Phase 56 constants
    PHASE = 56
    CORPUS_TRAIN_TOKENS = 12_277

    def __init__(
        self,
        unique_corpus_tokens: int = CORPUS_TRAIN_TOKENS,
        warn_epoch_threshold: float = 10.0,
        pause_epoch_threshold: float = 15.0,
        block_epoch_threshold: float = 25.0,
        concentration_threshold: float = 0.40,
        domain_concentration_threshold: float = 0.50,
        divergence_threshold: float = 0.25,
        repetition_threshold: float = 0.50,
        window_size: int = 100,
        capability_floor: float = 0.0,
        ood_degradation_threshold: float = 0.30,
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
        self.capability_floor = capability_floor
        self.ood_degradation_threshold = ood_degradation_threshold

        # Exposure tracking
        self.exposures: Dict[str, RecordExposureTelemetry] = {}
        self.domain_exposures: Dict[str, int] = collections.defaultdict(int)
        self.source_exposures: Dict[str, int] = collections.defaultdict(int)

        # Sequence window for repetition detection
        self.sequence_window: collections.deque = collections.deque(maxlen=window_size)

        # Counters
        self.total_tokens_seen: int = 0
        self.current_step: int = 0
        self.last_train_loss: Optional[float] = None
        self.last_val_loss: Optional[float] = None

        # Capability tracking (set externally at eval milestones)
        self.baseline_capability: float = 0.0
        self.current_capability: float = 0.0
        self.current_seen_score: float = 0.0
        self.current_ood_score: float = 0.0
        self.capability_milestones: List[CapabilityMilestone] = []

        # Guard state
        self.current_state: GuardAction = GuardAction.ALLOW
        self.state_history: List[Dict[str, Any]] = []
        self.halt_reason: Optional[str] = None

        # Telemetry log
        self.telemetry_log: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Core interface
    # ------------------------------------------------------------------

    def record_step_exposure(
        self,
        step: int,
        batch_records: List[Dict[str, Any]],
        tokens_in_batch: int,
        train_loss: Optional[float] = None,
        val_loss: Optional[float] = None,
    ) -> GuardAction:
        """Record one training step and evaluate guard policy.

        Returns the current GuardAction. If PAUSE or BLOCK, training must halt.
        """
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
                # Use 5-gram prefix for repetition window
                words = text.split()
                ngram = " ".join(words[:5]) if len(words) >= 5 else text[:32]
                self.sequence_window.append(ngram)

        action = self._evaluate_policy()
        if action != self.current_state or step % 10 == 0:
            self._record_state_event(step, action)

        return action

    def _evaluate_policy(self) -> GuardAction:
        """Fail-closed policy evaluation. Returns strictest triggered action."""
        epochs = self.get_effective_epochs()
        dominant_conc = self.get_dominant_concentration()
        domain_conc = self.get_domain_concentration()
        divergence = self.get_validation_divergence()
        repetition = self.get_repetition_ratio()

        # Hard BLOCK conditions
        if epochs >= self.block_epoch_threshold:
            self._set_halt_reason(f"Effective epochs {epochs:.2f} >= BLOCK threshold {self.block_epoch_threshold}")
            return GuardAction.BLOCK

        # PAUSE conditions (fail-closed)
        if epochs >= self.pause_epoch_threshold:
            self._set_halt_reason(f"Effective epochs {epochs:.2f} >= PAUSE threshold {self.pause_epoch_threshold}")
            return GuardAction.PAUSE

        if dominant_conc >= self.concentration_threshold:
            self._set_halt_reason(f"Dominant record concentration {dominant_conc:.4f} >= {self.concentration_threshold}")
            return GuardAction.PAUSE

        if domain_conc >= self.domain_concentration_threshold and len(self.domain_exposures) >= 3:
            self._set_halt_reason(f"Domain concentration {domain_conc:.4f} >= {self.domain_concentration_threshold}")
            return GuardAction.PAUSE

        if divergence >= self.divergence_threshold:
            self._set_halt_reason(f"Validation divergence {divergence:.4f} >= {self.divergence_threshold}")
            return GuardAction.PAUSE

        if repetition >= self.repetition_threshold:
            self._set_halt_reason(f"Sequence repetition ratio {repetition:.4f} >= {self.repetition_threshold}")
            return GuardAction.PAUSE

        # OOD degradation check (only after we have capability data)
        if self.current_seen_score > 0.05 and self.current_ood_score is not None:
            gap = self.current_seen_score - self.current_ood_score
            if gap > self.ood_degradation_threshold:
                self._set_halt_reason(
                    f"OOD degradation: seen={self.current_seen_score:.2f} - OOD={self.current_ood_score:.2f} = {gap:.2f} > {self.ood_degradation_threshold}"
                )
                return GuardAction.PAUSE

        # Clear halt reason if we're in ALLOW/WARN
        if self.halt_reason and (
            epochs < self.pause_epoch_threshold
            and dominant_conc < self.concentration_threshold
        ):
            self.halt_reason = None

        # Soft WARN conditions
        if epochs >= self.warn_epoch_threshold:
            return GuardAction.WARN
        if dominant_conc >= (self.concentration_threshold * 0.85):
            return GuardAction.WARN

        return GuardAction.ALLOW

    def _set_halt_reason(self, reason: str) -> None:
        if not self.halt_reason:
            self.halt_reason = reason

    def _record_state_event(self, step: int, action: GuardAction) -> None:
        event = {
            "step": step,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "previous_state": self.current_state.value,
            "new_state": action.value,
            "effective_epochs": self.get_effective_epochs(),
            "dominant_concentration": self.get_dominant_concentration(),
            "domain_concentration": self.get_domain_concentration(),
            "source_concentration": self.get_source_concentration(),
            "validation_divergence": self.get_validation_divergence(),
            "repetition_ratio": self.get_repetition_ratio(),
            "halt_reason": self.halt_reason,
        }
        if action != self.current_state:
            self.state_history.append(event)
        self.telemetry_log.append(event)
        self.current_state = action

    # ------------------------------------------------------------------
    # Metric accessors
    # ------------------------------------------------------------------

    def get_effective_epochs(self) -> float:
        return self.total_tokens_seen / self.unique_corpus_tokens

    def get_dominant_concentration(self) -> float:
        """Top-10% records' share of total exposures."""
        if len(self.exposures) < 10:
            return 0.0
        counts = sorted([r.exposure_count for r in self.exposures.values()], reverse=True)
        top_k = max(1, int(round(len(counts) * 0.10)))
        return sum(counts[:top_k]) / max(1, sum(counts))

    def get_domain_concentration(self) -> float:
        if not self.domain_exposures:
            return 0.0
        max_dom = max(self.domain_exposures.values())
        return max_dom / max(1, sum(self.domain_exposures.values()))

    def get_source_concentration(self) -> float:
        if not self.source_exposures:
            return 0.0
        max_src = max(self.source_exposures.values())
        return max_src / max(1, sum(self.source_exposures.values()))

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

    # ------------------------------------------------------------------
    # Control interface
    # ------------------------------------------------------------------

    def should_halt(self) -> bool:
        """Returns True if training must halt (PAUSE or BLOCK)."""
        return self.current_state in (GuardAction.PAUSE, GuardAction.BLOCK)

    def record_capability_milestone(
        self,
        milestone_id: str,
        score: float,
        seen_score: float,
        held_out_score: float,
        ood_score: float,
    ) -> None:
        """Record a capability evaluation result at a training milestone."""
        self.current_capability = score
        self.current_seen_score = seen_score
        self.current_ood_score = ood_score
        milestone = CapabilityMilestone(
            milestone_id=milestone_id,
            step=self.current_step,
            effective_epochs=self.get_effective_epochs(),
            score=score,
            seen_score=seen_score,
            held_out_score=held_out_score,
            ood_score=ood_score,
            train_loss=self.last_train_loss,
            val_loss=self.last_val_loss,
        )
        self.capability_milestones.append(milestone)

    def compute_config_hash(self) -> str:
        """Return SHA-256 of the guard configuration for audit."""
        config_str = json.dumps({
            "unique_corpus_tokens": self.unique_corpus_tokens,
            "warn_epoch_threshold": self.warn_epoch_threshold,
            "pause_epoch_threshold": self.pause_epoch_threshold,
            "block_epoch_threshold": self.block_epoch_threshold,
            "concentration_threshold": self.concentration_threshold,
            "domain_concentration_threshold": self.domain_concentration_threshold,
            "divergence_threshold": self.divergence_threshold,
            "repetition_threshold": self.repetition_threshold,
        }, sort_keys=True)
        return hashlib.sha256(config_str.encode()).hexdigest()

    def get_status_summary(self) -> Dict[str, Any]:
        return {
            "phase": self.PHASE,
            "current_state": self.current_state.value,
            "halt_reason": self.halt_reason,
            "total_tokens_seen": self.total_tokens_seen,
            "unique_corpus_tokens": self.unique_corpus_tokens,
            "effective_epochs": round(self.get_effective_epochs(), 4),
            "dominant_concentration": round(self.get_dominant_concentration(), 4),
            "domain_concentration": round(self.get_domain_concentration(), 4),
            "source_concentration": round(self.get_source_concentration(), 4),
            "validation_divergence": round(self.get_validation_divergence(), 4),
            "repetition_ratio": round(self.get_repetition_ratio(), 4),
            "tracked_records": len(self.exposures),
            "tracked_domains": len(self.domain_exposures),
            "tracked_sources": len(self.source_exposures),
            "current_step": self.current_step,
            "state_history": self.state_history,
            "capability_milestones": [
                {
                    "id": m.milestone_id,
                    "step": m.step,
                    "effective_epochs": m.effective_epochs,
                    "score": m.score,
                    "seen": m.seen_score,
                    "held_out": m.held_out_score,
                    "ood": m.ood_score,
                    "train_loss": m.train_loss,
                    "val_loss": m.val_loss,
                }
                for m in self.capability_milestones
            ],
            "config_hash": self.compute_config_hash(),
        }

    def get_telemetry_jsonl(self) -> str:
        """Return telemetry as JSONL string for audit log."""
        lines = []
        for entry in self.telemetry_log:
            lines.append(json.dumps(entry, ensure_ascii=False))
        return "\n".join(lines)
