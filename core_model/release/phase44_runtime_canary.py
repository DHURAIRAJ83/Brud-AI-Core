"""Phase 44 — Live Internal Canary Runtime & Scope Isolation Engine.

Implements Workstreams 3, 4 & 10:
- Strict Default Traffic: 0.0%
- Strict Maximum Traffic Ceiling: 1.0% (0.01)
- Scope Routing Enforcement:
  - 'public_chat' scope: strictly barred from candidate; routes exclusively to known-good model.
  - 'internal_canary' scope: routes to candidate ONLY IF two-person governance is approved.
  - Candidate requests targeting 'public_chat' raise a critical ScopeViolationError.
  - Unauthorized or unknown scopes are rejected.
- Production Shadow Mode:
  - Concurrently evaluates candidate on internal traffic.
  - Strictly prevents candidate responses from reaching public users.
  - Records candidate latency and status for telemetry.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from core_model.release.phase44_runtime_governance import RuntimeGovernanceController


class ScopeViolationError(PermissionError):
    """Raised when a candidate model is illegally targeted for public chat."""
    pass


@dataclass
class RoutingDecision:
    allowed: bool
    target_model_id: str
    scope: str
    traffic_percentage: float
    reason: str
    is_shadow: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RuntimeInternalCanary:
    """Controls runtime request routing and enforces strict scope isolation between public chat and internal canary."""

    MAX_INTERNAL_TRAFFIC = 0.01  # 1.0% maximum internal canary ceiling
    KNOWN_GOOD_MODEL_ID = "0.1.0-synthetic-test"

    def __init__(
        self,
        candidate_model_id: str,
        governance_controller: RuntimeGovernanceController,
        traffic_percentage: float = 0.0,
        shadow_enabled: bool = False,
    ) -> None:
        if traffic_percentage < 0.0 or traffic_percentage > self.MAX_INTERNAL_TRAFFIC:
            raise ValueError(
                f"Traffic percentage {traffic_percentage} exceeds allowed bounds [0.0, {self.MAX_INTERNAL_TRAFFIC}]"
            )
        self.candidate_model_id = candidate_model_id
        self.governance_controller = governance_controller
        self._traffic_percentage = traffic_percentage
        self.shadow_enabled = shadow_enabled
        self.is_public_chat_eligible = False  # Immutable safety invariant

    @property
    def traffic_percentage(self) -> float:
        return self._traffic_percentage

    def set_traffic_percentage(self, percentage: float, authorization_token: str) -> None:
        """Sets internal canary traffic percentage with strict bounds and governance checks."""
        if percentage > self.MAX_INTERNAL_TRAFFIC:
            raise ValueError(
                f"Traffic percentage {percentage * 100:.1f}% exceeds 1.0% maximum internal ceiling"
            )
        if percentage < 0.0:
            raise ValueError("Traffic percentage cannot be negative")

        # Must have two-person approval before non-zero traffic can be activated
        if percentage > 0.0:
            if self.governance_controller.current_state not in {
                "ADMIN_APPROVED",
                "RUNTIME_VALIDATION",
                "INTERNAL_CANARY_READY",
                "INTERNAL_CANARY_ACTIVE",
                "INTERNAL_CANARY_QUALIFIED",
            }:
                raise PermissionError(
                    f"Cannot enable traffic: Governance state '{self.governance_controller.current_state}' not approved"
                )

        self._traffic_percentage = percentage
        if percentage > 0.0 and self.governance_controller.current_state != "INTERNAL_CANARY_ACTIVE":
            self.governance_controller.transition_to("INTERNAL_CANARY_ACTIVE", actor="canary_runtime")

    def route_request(self, scope: str, request_payload: dict[str, Any] | None = None) -> RoutingDecision:
        """Determines model target based on scope, traffic, and governance verification."""
        # Rule 2: Public Chat isolation invariant
        if scope == "public_chat":
            # If request explicitly demands candidate in public chat, reject with critical error
            if request_payload and request_payload.get("requested_model_id") == self.candidate_model_id:
                raise ScopeViolationError("CRITICAL: Candidate model cannot be routed to Public Chat.")
            return RoutingDecision(
                allowed=True,
                target_model_id=self.KNOWN_GOOD_MODEL_ID,
                scope=scope,
                traffic_percentage=1.0,
                reason="Public Chat routed to verified production fallback model",
            )

        # Rule 3 & 4: Internal Canary routing
        if scope == "internal_canary":
            if self.governance_controller.current_state not in {
                "INTERNAL_CANARY_ACTIVE",
                "INTERNAL_CANARY_READY",
                "INTERNAL_CANARY_QUALIFIED",
            }:
                return RoutingDecision(
                    allowed=False,
                    target_model_id=self.KNOWN_GOOD_MODEL_ID,
                    scope=scope,
                    traffic_percentage=0.0,
                    reason="REJECT: Governance two-person approval required for internal canary",
                )

            if self._traffic_percentage <= 0.0:
                return RoutingDecision(
                    allowed=False,
                    target_model_id=self.KNOWN_GOOD_MODEL_ID,
                    scope=scope,
                    traffic_percentage=0.0,
                    reason="REJECT: Internal canary traffic is currently 0.0%",
                )

            return RoutingDecision(
                allowed=True,
                target_model_id=self.candidate_model_id,
                scope=scope,
                traffic_percentage=self._traffic_percentage,
                reason=f"Candidate model authorized for internal canary ({self._traffic_percentage * 100:.1f}%)",
            )

        # Unknown or unauthorized scope
        return RoutingDecision(
            allowed=False,
            target_model_id=self.KNOWN_GOOD_MODEL_ID,
            scope=scope,
            traffic_percentage=0.0,
            reason=f"REJECT: Unauthorized scope '{scope}'",
        )

    def execute_shadow_evaluation(
        self,
        prompt: str,
        candidate_inference_fn: Callable[[str], str],
    ) -> dict[str, Any]:
        """Executes candidate model evaluation in shadow mode without exposing output to public users."""
        if not self.shadow_enabled:
            return {"shadow_executed": False, "reason": "Shadow mode disabled"}

        t0 = time.monotonic()
        try:
            output = candidate_inference_fn(prompt)
            latency_ms = (time.monotonic() - t0) * 1000.0
            return {
                "shadow_executed": True,
                "latency_ms": latency_ms,
                "output_length": len(output),
                "status": "success",
                "user_exposed": False,  # Safety invariant
            }
        except Exception as e:
            latency_ms = (time.monotonic() - t0) * 1000.0
            return {
                "shadow_executed": True,
                "latency_ms": latency_ms,
                "status": "error",
                "error": str(e),
                "user_exposed": False,
            }
