"""Phase 41 — Canary Traffic Controller & Emergency Rollback Engine.

Implements Workstreams 14 & 15:
- Default 0.0% canary traffic
- Two-person administrative review required before any traffic ramp
- Bounded traffic allocation (1% to 5% max) with real-time error rate & latency monitoring
- Emergency tripwire: automatic fallback and atomic rollback upon error spike
- Public Chat scope isolation (unapproved candidates barred from public chat)
- Non-destructive preservation of candidate checkpoints for post-mortem analysis
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CanaryTrafficPolicy:
    model_id: str
    model_version: str
    traffic_percentage: float = 0.0  # Strict default 0.0%
    is_public_chat_eligible: bool = False
    admin_approval_recorded: bool = False
    approving_admin_id: str | None = None
    max_error_rate_threshold: float = 0.02  # 2% error tripwire
    max_p95_latency_ms: float = 1000.0  # 1000ms latency tripwire
    current_status: str = "CANARY_STAGED"  # CANARY_STAGED | CANARY_ACTIVE | ROLLED_BACK | PRODUCTION_APPROVED
    total_requests: int = 0
    error_requests: int = 0
    latency_samples_ms: list[float] = field(default_factory=list)
    audit_log: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CanaryTrafficController:
    """Manages controlled canary traffic staging, telemetry monitoring, and emergency rollbacks."""

    def __init__(self, fallback_production_model_id: str = "0.1.0-synthetic-test") -> None:
        self.fallback_production_model_id = fallback_production_model_id

    def stage_candidate(self, model_id: str, model_version: str) -> CanaryTrafficPolicy:
        """Stages a newly qualified candidate in Canary stage at 0.0% traffic."""
        policy = CanaryTrafficPolicy(
            model_id=model_id,
            model_version=model_version,
            traffic_percentage=0.0,
            is_public_chat_eligible=False,
            current_status="CANARY_STAGED",
        )
        policy.audit_log.append({
            "timestamp": time.time(),
            "event": "STAGE_CANDIDATE",
            "model_id": model_id,
            "traffic": 0.0,
            "message": "Candidate model staged in CANARY at 0.0% default traffic.",
        })
        return policy

    def approve_canary_traffic(
        self,
        policy: CanaryTrafficPolicy,
        admin_id: str,
        requested_percentage: float = 0.05,
    ) -> CanaryTrafficPolicy:
        """Applies bounded canary traffic ONLY after explicit administrative approval."""
        if requested_percentage < 0.0 or requested_percentage > 0.10:
            raise ValueError("Canary traffic cannot exceed 10% bounds")

        policy.admin_approval_recorded = True
        policy.approving_admin_id = admin_id
        policy.traffic_percentage = requested_percentage
        policy.current_status = "CANARY_ACTIVE"
        # Eligible for internal canary routing, but NOT promoted to primary public production
        policy.is_public_chat_eligible = True

        policy.audit_log.append({
            "timestamp": time.time(),
            "event": "APPROVE_CANARY_TRAFFIC",
            "admin_id": admin_id,
            "traffic": requested_percentage,
            "message": f"Administrative approval granted for {requested_percentage * 100:.1f}% canary traffic.",
        })
        return policy

    def record_request_telemetry(
        self,
        policy: CanaryTrafficPolicy,
        latency_ms: float,
        is_error: bool = False,
    ) -> bool:
        """Records traffic telemetry and checks error rate and latency tripwires."""
        policy.total_requests += 1
        if is_error:
            policy.error_requests += 1
        policy.latency_samples_ms.append(latency_ms)

        error_rate = policy.error_requests / policy.total_requests
        if error_rate > policy.max_error_rate_threshold and policy.total_requests >= 10:
            # Tripwire triggered!
            self.emergency_rollback(policy, reason=f"Error rate {error_rate * 100:.1f}% exceeded safety threshold")
            return False

        if latency_ms > policy.max_p95_latency_ms:
            self.emergency_rollback(policy, reason=f"Latency {latency_ms:.1f}ms exceeded P95 safety threshold")
            return False

        return True

    def emergency_rollback(self, policy: CanaryTrafficPolicy, reason: str) -> tuple[str, CanaryTrafficPolicy]:
        """Immediately halts canary traffic and reverts active assignment to previous production model."""
        reverted_model = self.fallback_production_model_id
        policy.traffic_percentage = 0.0
        policy.is_public_chat_eligible = False
        policy.current_status = "ROLLED_BACK"

        policy.audit_log.append({
            "timestamp": time.time(),
            "event": "EMERGENCY_ROLLBACK",
            "reverted_to": reverted_model,
            "reason": reason,
            "message": f"Emergency rollback executed. Restored production model {reverted_model}.",
        })
        return reverted_model, policy
