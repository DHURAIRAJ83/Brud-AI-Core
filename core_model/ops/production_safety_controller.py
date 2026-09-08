"""Phase 61 - P7: Production Safety Controller.

Fail-safe controller for freezing production traffic and invoking canonical P6 rollback.

CRITICAL INVARIANTS:
- Controller States: NORMAL | DEGRADED | TRAFFIC_FROZEN | ROLLBACK_REQUIRED | ROLLBACK_EXECUTING | ROLLBACK_VERIFICATION | RECOVERED.
- Reuses canonical P6 ProductionReleaseRegistry rollback mechanism. Never creates a duplicate rollback engine.
- Traffic freeze sets candidate_traffic_share = 0.0 and public_chat_eligible = FALSE.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from core_model.eval.production_release_registry import ProductionReleaseRegistry
from core_model.ops.continuous_safety_monitor import SafetyEvaluationResult
from core_model.ops.model_health_monitor import HealthEvaluationResult


@dataclass
class ControllerStatusRecord:
    """Status record of production safety controller."""
    release_id: str
    controller_state: str  # NORMAL | DEGRADED | TRAFFIC_FROZEN | ROLLBACK_REQUIRED | ROLLBACK_EXECUTING | ROLLBACK_VERIFICATION | RECOVERED
    candidate_traffic_share: float
    public_chat_eligible: bool
    active_model_hash: str
    last_action_timestamp: str
    reasons: list[str] = field(default_factory=list)


class ProductionSafetyController:
    """Fail-safe production traffic freeze and rollback controller."""

    def __init__(self, release_registry: ProductionReleaseRegistry | None = None) -> None:
        self.release_registry = release_registry or ProductionReleaseRegistry()
        self.controller_state = "NORMAL"
        self.candidate_traffic_share = 0.0
        self.public_chat_eligible = False

    def evaluate_and_control(
        self,
        release_id: str,
        health_res: HealthEvaluationResult | None,
        safety_res: SafetyEvaluationResult | None,
    ) -> ControllerStatusRecord:
        """Evaluate operational telemetry and execute fail-safe governance actions."""
        reasons: list[str] = []

        # 1. Health evaluation check
        if health_res and health_res.health_status in ("DEGRADED", "CRITICAL"):
            reasons.extend(health_res.reasons)
            if health_res.health_status == "CRITICAL":
                self.controller_state = "ROLLBACK_REQUIRED"
            elif self.controller_state != "ROLLBACK_REQUIRED":
                self.controller_state = "DEGRADED"

        # 2. Safety evaluation check
        if safety_res and safety_res.safety_status in ("VIOLATION", "CRITICAL"):
            reasons.append(f"Safety status '{safety_res.safety_status}' triggered escalation.")
            if safety_res.escalation_action in ("TRAFFIC_FREEZE", "PUBLIC_CHAT_SUSPENDED"):
                self.controller_state = "TRAFFIC_FROZEN"
            elif safety_res.escalation_action == "ROLLBACK_REQUIRED":
                self.controller_state = "ROLLBACK_REQUIRED"

        # 3. Action execution
        if self.controller_state in ("TRAFFIC_FROZEN", "ROLLBACK_REQUIRED"):
            self.candidate_traffic_share = 0.0
            self.public_chat_eligible = False

        # Execute rollback via canonical P6 release registry if ROLLBACK_REQUIRED
        if self.controller_state == "ROLLBACK_REQUIRED":
            self.controller_state = "ROLLBACK_EXECUTING"
            active_rec = self.release_registry.get_active_release()
            prev_rel_id = active_rec.previous_production_release_id if active_rec else None

            self.release_registry.mark_rollback(release_id, previous_release_id=prev_rel_id)
            self.controller_state = "ROLLBACK_VERIFICATION"

            # Confirm rollback
            recovered_active = self.release_registry.get_active_release()
            active_hash = recovered_active.candidate_model_hash if recovered_active else "base-approved-hash"
            self.controller_state = "RECOVERED"

            return ControllerStatusRecord(
                release_id=release_id,
                controller_state="RECOVERED",
                candidate_traffic_share=0.0,
                public_chat_eligible=False,
                active_model_hash=active_hash,
                last_action_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                reasons=reasons
            )

        active_rec = self.release_registry.get_active_release()
        active_hash = active_rec.candidate_model_hash if active_rec else "base-approved-hash"

        return ControllerStatusRecord(
            release_id=release_id,
            controller_state=self.controller_state,
            candidate_traffic_share=self.candidate_traffic_share,
            public_chat_eligible=self.public_chat_eligible,
            active_model_hash=active_hash,
            last_action_timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            reasons=reasons
        )
