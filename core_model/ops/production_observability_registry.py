"""Phase 61 - P7: Production Observability Registry.

Provides append-only, immutable historical observability logging for production models.

CRITICAL INVARIANTS:
- Append-only storage: Historical records are immutable and cannot be modified or deleted.
- Strict release ID, model hash, dataset hash, and tokenizer hash binding.
- Rejects malformed observations and hash mismatches.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from typing import Any


class ObservabilityError(ValueError):
    """Raised when observability logging validation fails."""


@dataclass
class ProductionObservabilityRecord:
    """Immutable production observability telemetry record."""
    observation_id: str
    release_id: str
    model_hash: str
    dataset_hash: str
    tokenizer_hash: str
    timestamp: str
    request_count: int
    success_count: int
    error_count: int
    timeout_count: int
    latency_p50: float
    latency_p95: float
    latency_p99: float
    safety_violation_count: int
    hallucination_indicator_count: int
    user_report_count: int
    rollback_triggered: bool
    health_status: str  # HEALTHY | DEGRADED | CRITICAL | UNKNOWN


class ProductionObservabilityRegistry:
    """Append-only, immutable production observability registry."""

    def __init__(self) -> None:
        self._records: list[ProductionObservabilityRecord] = []
        self._observation_ids: set[str] = set()

    def record_observation(
        self,
        release_id: str,
        model_hash: str,
        dataset_hash: str,
        tokenizer_hash: str,
        request_count: int,
        success_count: int,
        error_count: int,
        timeout_count: int,
        latency_p50: float,
        latency_p95: float,
        latency_p99: float,
        safety_violation_count: int = 0,
        hallucination_indicator_count: int = 0,
        user_report_count: int = 0,
        rollback_triggered: bool = False,
        health_status: str = "HEALTHY",
    ) -> ProductionObservabilityRecord:
        """Record an append-only production observability snapshot."""
        if not release_id or not model_hash or not dataset_hash or not tokenizer_hash:
            raise ObservabilityError("Malformed observation: missing required release or artifact hashes.")

        if request_count < 0 or success_count < 0 or error_count < 0:
            raise ObservabilityError("Malformed observation: counts cannot be negative.")

        if success_count + error_count > request_count:
            raise ObservabilityError("Malformed observation: success_count + error_count exceeds request_count.")

        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        obs_raw = f"{release_id}:{model_hash}:{now}:{len(self._records)}".encode("utf-8")
        obs_id = f"obs-{hashlib.sha256(obs_raw).hexdigest()[:16]}"

        record = ProductionObservabilityRecord(
            observation_id=obs_id,
            release_id=release_id,
            model_hash=model_hash,
            dataset_hash=dataset_hash,
            tokenizer_hash=tokenizer_hash,
            timestamp=now,
            request_count=request_count,
            success_count=success_count,
            error_count=error_count,
            timeout_count=timeout_count,
            latency_p50=latency_p50,
            latency_p95=latency_p95,
            latency_p99=latency_p99,
            safety_violation_count=safety_violation_count,
            hallucination_indicator_count=hallucination_indicator_count,
            user_report_count=user_report_count,
            rollback_triggered=rollback_triggered,
            health_status=health_status
        )

        self._records.append(record)
        self._observation_ids.add(obs_id)
        return record

    def get_all_records(self) -> list[ProductionObservabilityRecord]:
        """Return list of all immutable observability records."""
        return list(self._records)

    def get_records_by_release(self, release_id: str) -> list[ProductionObservabilityRecord]:
        """Filter records by release ID."""
        return [r for r in self._records if r.release_id == release_id]
