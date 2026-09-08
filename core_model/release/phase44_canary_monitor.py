"""Phase 44 — Canary Health Monitor, Telemetry Logger & Atomic Rollback Engine.

Implements Workstreams 5, 6, 7 & 8:
- Machine-Readable Telemetry:
  Logs structured observations to phase44_canary_telemetry.jsonl.
- Automated Anomaly Tripwires:
  - Error rate > 2.0% (after minimum window of 10 requests)
  - P95 latency > 1,000 ms
  - Model loading failure
  - Checkpoint integrity mismatch
  - Critical scope violation (candidate attempted in public chat)
- Atomic Rollback:
  - Immediately cuts candidate traffic to 0.0%
  - Restores active assignment to 0.1.0-synthetic-test
  - Non-destructively preserves candidate artifacts, deployment bundle, and telemetry
  - Transitions governance state to ROLLED_BACK
  - Requires fresh two-person approval before reactivation
  - Fails closed on error.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core_model.release.phase44_runtime_canary import RuntimeInternalCanary
from core_model.release.phase44_runtime_governance import RuntimeGovernanceController


@dataclass
class CanaryObservation:
    timestamp: str
    release_id: str
    model_sha256: str
    scope: str
    traffic_percentage: float
    request_id: str
    latency_ms: float
    status: str  # success | error
    error: str | None = None
    rollback_triggered: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RuntimeCanaryMonitor:
    """Monitors live canary runtime telemetry, calculates rolling health metrics, and triggers atomic rollback."""

    ERROR_RATE_THRESHOLD = 0.02  # 2.0%
    P95_LATENCY_THRESHOLD_MS = 1000.0  # 1,000 ms

    def __init__(
        self,
        canary: RuntimeInternalCanary,
        governance_controller: RuntimeGovernanceController,
        telemetry_file: Path,
    ) -> None:
        self.canary = canary
        self.governance = governance_controller
        self.telemetry_file = telemetry_file
        self.observations: list[CanaryObservation] = []
        self._rollback_occurred = False
        self._last_rollback_details: dict[str, Any] | None = None

    @property
    def rollback_occurred(self) -> bool:
        return self._rollback_occurred

    @property
    def last_rollback_details(self) -> dict[str, Any] | None:
        return self._last_rollback_details

    def record_observation(self, obs: CanaryObservation) -> None:
        """Appends observation to in-memory list and writes to JSONL telemetry file."""
        self.observations.append(obs)
        line = json.dumps(obs.to_dict()) + "\n"
        with self.telemetry_file.open("a", encoding="utf-8") as f:
            f.write(line)

        # Check tripwires on every observation
        self.check_and_enforce_tripwires()

    def calculate_metrics(self) -> dict[str, float]:
        """Calculates current rolling error rate and P95 latency."""
        if not self.observations:
            return {"error_rate": 0.0, "p95_latency_ms": 0.0, "total_requests": 0}

        total = len(self.observations)
        errors = sum(1 for o in self.observations if o.status == "error")
        error_rate = errors / total

        latencies = sorted(o.latency_ms for o in self.observations)
        p95_index = int(0.95 * total)
        p95_index = min(p95_index, total - 1)
        p95_latency = latencies[p95_index]

        return {
            "error_rate": error_rate,
            "p95_latency_ms": p95_latency,
            "total_requests": total,
        }

    def check_and_enforce_tripwires(self) -> bool:
        """Evaluates health thresholds and triggers atomic rollback if any tripwire is breached."""
        if not self.observations or self._rollback_occurred:
            return False

        metrics = self.calculate_metrics()

        # Tripwire 1: Error rate > 2% (requires at least 10 requests to avoid small-sample false alarms)
        if metrics["total_requests"] >= 10 and metrics["error_rate"] > self.ERROR_RATE_THRESHOLD:
            self.execute_atomic_rollback(
                f"Tripwire: Error rate {metrics['error_rate'] * 100:.1f}% exceeded 2.0% bound"
            )
            return True

        # Tripwire 2: P95 latency > 1,000 ms
        if metrics["total_requests"] >= 5 and metrics["p95_latency_ms"] > self.P95_LATENCY_THRESHOLD_MS:
            self.execute_atomic_rollback(
                f"Tripwire: P95 latency {metrics['p95_latency_ms']:.1f}ms exceeded 1,000ms bound"
            )
            return True

        return False

    def trigger_model_load_failure(self, model_id: str, error_msg: str) -> None:
        """Invoked when model loading fails; triggers immediate rollback."""
        self.execute_atomic_rollback(f"Tripwire: Model loading failed for {model_id}: {error_msg}")

    def trigger_integrity_failure(self, details: str) -> None:
        """Invoked when SHA-256 integrity check fails; triggers immediate rollback."""
        self.execute_atomic_rollback(f"Tripwire: Checkpoint integrity failure: {details}")

    def trigger_scope_violation(self, details: str) -> None:
        """Invoked when candidate request breaches scope boundaries."""
        self.execute_atomic_rollback(f"CRITICAL TRIPWIRE: Scope violation detected: {details}")

    def execute_atomic_rollback(self, reason: str) -> dict[str, Any]:
        """Executes non-destructive atomic rollback restoring known-good model and zeroing traffic."""
        try:
            # 1. Zero out candidate traffic immediately
            self.canary._traffic_percentage = 0.0

            # 2. Transition governance to ROLLED_BACK
            self.governance.transition_to("ROLLED_BACK", actor="canary_monitor")

            # 3. Record details
            self._rollback_occurred = True
            details = {
                "timestamp": time.time(),
                "rollback_reason": reason,
                "candidate_traffic": 0.0,
                "active_production_model": RuntimeInternalCanary.KNOWN_GOOD_MODEL_ID,
                "candidate_model_id": self.canary.candidate_model_id,
                "candidate_artifacts_preserved": True,
                "audit_logs_preserved": True,
                "telemetry_preserved": True,
                "reactivation_allowed": False,  # Requires new two-person approval
            }
            self._last_rollback_details = details

            # Record a final telemetry event indicating rollback
            obs = CanaryObservation(
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                release_id=self.governance.release_id,
                model_sha256="unknown",
                scope="internal_canary",
                traffic_percentage=0.0,
                request_id="rollback-event",
                latency_ms=0.0,
                status="error",
                error=reason,
                rollback_triggered=True,
            )
            line = json.dumps(obs.to_dict()) + "\n"
            with self.telemetry_file.open("a", encoding="utf-8") as f:
                f.write(line)

            return details
        except Exception as e:
            # Fail closed: ensure traffic is 0.0 regardless of exceptions
            self.canary._traffic_percentage = 0.0
            return {
                "status": "FAIL_CLOSED",
                "error": str(e),
                "candidate_traffic": 0.0,
                "active_production_model": RuntimeInternalCanary.KNOWN_GOOD_MODEL_ID,
            }
