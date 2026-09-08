"""Phase 61 - P7: Model Health Monitor Engine.

Evaluates deterministic health status from production observability telemetry.

CRITICAL INVARIANTS:
- Health States: HEALTHY | DEGRADED | CRITICAL | UNKNOWN.
- FAIL-CLOSED REQUIREMENT: Unknown, missing critical, or malformed telemetry strictly defaults to DEGRADED or CRITICAL. Never classify unverified telemetry as HEALTHY.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core_model.ops.production_observability_registry import ProductionObservabilityRecord


@dataclass
class HealthEvaluationResult:
    """Outcome of production model health evaluation."""
    health_status: str  # HEALTHY | DEGRADED | CRITICAL | UNKNOWN
    error_rate: float
    timeout_rate: float
    latency_p95: float
    safety_violations: int
    reasons: list[str]


class ModelHealthMonitor:
    """Evaluates production model health with fail-closed governance."""

    def __init__(
        self,
        max_error_rate_degraded: float = 0.02,
        max_error_rate_critical: float = 0.05,
        max_latency_p95_ms: float = 250.0,
    ) -> None:
        self.max_error_rate_degraded = max_error_rate_degraded
        self.max_error_rate_critical = max_error_rate_critical
        self.max_latency_p95_ms = max_latency_p95_ms

    def evaluate_health(
        self,
        record: ProductionObservabilityRecord | None,
    ) -> HealthEvaluationResult:
        """Evaluate model health status. Fails closed on missing or invalid telemetry."""
        reasons: list[str] = []

        if record is None:
            return HealthEvaluationResult(
                health_status="CRITICAL",
                error_rate=1.0,
                timeout_rate=1.0,
                latency_p95=9999.0,
                safety_violations=0,
                reasons=["Fail-Closed: Telemetry record is missing or None."]
            )

        if record.request_count <= 0:
            return HealthEvaluationResult(
                health_status="DEGRADED",
                error_rate=0.0,
                timeout_rate=0.0,
                latency_p95=record.latency_p95,
                safety_violations=record.safety_violation_count,
                reasons=["Fail-Closed: Zero requests recorded, health status UNKNOWN -> DEGRADED."]
            )

        error_rate = round(record.error_count / record.request_count, 4)
        timeout_rate = round(record.timeout_count / record.request_count, 4)

        if record.safety_violation_count > 0:
            reasons.append(f"Safety violations detected: {record.safety_violation_count}")

        if error_rate >= self.max_error_rate_critical:
            reasons.append(f"Error rate {error_rate:.4f} >= critical threshold {self.max_error_rate_critical:.4f}")

        if timeout_rate >= self.max_error_rate_critical:
            reasons.append(f"Timeout rate {timeout_rate:.4f} >= critical threshold {self.max_error_rate_critical:.4f}")

        if record.latency_p95 > self.max_latency_p95_ms * 2.0:
            reasons.append(f"Latency P95 {record.latency_p95:.1f}ms severely exceeds max threshold {self.max_latency_p95_ms:.1f}ms")

        # Determine state
        if record.safety_violation_count > 0 or error_rate >= self.max_error_rate_critical or timeout_rate >= self.max_error_rate_critical:
            status = "CRITICAL"
        elif error_rate >= self.max_error_rate_degraded or record.latency_p95 > self.max_latency_p95_ms:
            status = "DEGRADED"
            if error_rate >= self.max_error_rate_degraded:
                reasons.append(f"Error rate {error_rate:.4f} >= degraded threshold {self.max_error_rate_degraded:.4f}")
            if record.latency_p95 > self.max_latency_p95_ms:
                reasons.append(f"Latency P95 {record.latency_p95:.1f}ms > threshold {self.max_latency_p95_ms:.1f}ms")
        else:
            status = "HEALTHY"

        return HealthEvaluationResult(
            health_status=status,
            error_rate=error_rate,
            timeout_rate=timeout_rate,
            latency_p95=record.latency_p95,
            safety_violations=record.safety_violation_count,
            reasons=reasons
        )
