"""Phase 17: Public Chat Capability Gate — Policy & Observation Layer.

This module is the ONLY new execution layer Phase 17 introduces.

Architecture contract:
  - Consumes: Phase 15 process_text() → NLPResult
  - Consumes: Phase 16 route_capability() → RoutingDecision
  - Produces:  GateDecision (allowed, denial_reason, plain-dict audit_payload)

Critical invariants (read before any edit):
  ✅ Gate produces a GateDecision — NEVER executes the selected capability.
  ✅ Gate is called before PublicChatRoutingService; it does NOT replace it.
  ✅ API route logs gate.audit_payload but does NOT short-circuit the pipeline.
  ✅ Blocked gate requests still go through the existing safety pipeline
     (defense-in-depth — two independent gates).
  ✅ All audit data is serialized to plain dicts — no frozen dataclasses inside
     audit_payload so JSON serialization is always safe.
  ❌ No database reads or writes.
  ❌ No network calls.
  ❌ No subprocess or os.system.
  ❌ No eval / exec.
  ❌ No background workers, schedulers, queues, or cron.
  ❌ No tool invocation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core_model.capabilities.capability_matrix import get_capability
from core_model.capabilities.gate_observability import (
    build_gate_decided_payload,
    build_nlp_trace,
    build_routing_trace,
)
from core_model.capabilities.smart_router import RoutingDecision, route_capability
from core_model.nlp.text_processor import NLPResult, process_text

# ---------------------------------------------------------------------------
# Phase 17 policy constants (read-only)
# ---------------------------------------------------------------------------

#: Capabilities that must NEVER be routed through the public chat context.
#: This is the authoritative Phase 17 public/admin boundary set.
#: Every id here must also have ``supports_public_chat=False`` in the matrix.
_ADMIN_ONLY_CAPABILITY_IDS: frozenset[str] = frozenset(
    {
        "admin_assistant_governance",
        "automation_evaluation",
        "manual_automation_execution",
        "tool_execution",
        "data_studio_chunking",
        "external_ai_provider_gateway",
        "incremental_training",
        "autonomous_execution",
    }
)

#: Minimum routing confidence accepted by the gate.
#: Requests below this threshold are fail-closed regardless of capability.
_MINIMUM_CONFIDENCE = 0.60

# ---------------------------------------------------------------------------
# GateDecision — immutable result produced by evaluate_public_capability_gate()
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateDecision:
    """Immutable result of one Phase 17 gate evaluation.

    Attributes:
        allowed: True = NLP + routing analysis suggests the request is safe
            for the public chat pipeline. False = gate policy says blocked.
            In both cases the *existing* PublicChatRoutingService will still
            run its own independent safety checks (defense-in-depth).
        routing_decision: The Phase 16 RoutingDecision object.
        nlp_result: The Phase 15 NLPResult object.
        denial_reason: Non-None only when allowed=False; describes why the
            gate policy flagged this request.
        audit_payload: Plain-dict, JSON-serializable observability trace
            covering NLP classification, routing decision, and gate verdict.
            Never contains frozen dataclass instances.
    """

    allowed: bool
    routing_decision: RoutingDecision
    nlp_result: NLPResult
    denial_reason: str | None
    audit_payload: dict[str, Any]


# ---------------------------------------------------------------------------
# Internal policy helpers — pure functions, no side effects
# ---------------------------------------------------------------------------


def _is_admin_only_capability(routing_decision: RoutingDecision) -> tuple[bool, str]:
    """Returns (is_admin_only, reason).

    A capability is admin-only when:
    1. Its ID is in the hard-coded _ADMIN_ONLY_CAPABILITY_IDS set, OR
    2. The CapabilityDefinition explicitly has supports_public_chat=False.
    """
    cap_id = routing_decision.selected_capability_id
    if cap_id is None:
        return False, ""
    if cap_id in _ADMIN_ONLY_CAPABILITY_IDS:
        return True, f"admin_only_capability:{cap_id}"
    cap = get_capability(cap_id)
    if cap is not None and not cap.supports_public_chat:
        return True, f"capability_not_public_safe:{cap_id}"
    return False, ""


def _evaluate_gate_policy(
    nlp_result: NLPResult,
    routing_decision: RoutingDecision,
) -> tuple[bool, str | None]:
    """Pure policy evaluation. Returns (allowed, denial_reason | None).

    Gate blocks when ANY of the following is true:
    - Empty / invalid input (NLP returned unknown with zero confidence)
    - Routing failed closed (no capability matched with sufficient confidence)
    - Routing selected an admin-only capability
    - Routing selected a capability not executable for public context
    - Routing selected a high/critical risk capability in public context
    - Destructive intent detected in public context
    """
    # 1. Empty / purely non-linguistic input
    if not nlp_result.original_text or not nlp_result.original_text.strip():
        return False, "empty_or_invalid_input"

    # 2. Routing failed closed (no match or low confidence)
    if routing_decision.selected_capability_id is None:
        return False, "routing_failed_closed:insufficient_confidence"

    if routing_decision.confidence < _MINIMUM_CONFIDENCE:
        return False, f"low_confidence:{routing_decision.confidence:.2f}"

    # 3. Admin-only capability
    is_admin, admin_reason = _is_admin_only_capability(routing_decision)
    if is_admin:
        return False, admin_reason

    # 4. Routing decision itself says not executable for this context
    if not routing_decision.executable:
        blocking = ":".join(routing_decision.blocking_reasons) or "not_executable"
        return False, f"not_executable:{blocking}"

    # 5. High/critical risk in public context
    if routing_decision.risk_level in {"high", "critical"}:
        return False, f"risk_too_high_for_public:{routing_decision.risk_level}"

    # 6. Destructive intent flagged
    if "destructive_intent_detected_governance_required" in routing_decision.warnings:
        return False, "destructive_intent_in_public_context"

    return True, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def evaluate_public_capability_gate(
    request_text: str,
    *,
    caller_context: str = "public_chat",
    user_role: str = "none",
) -> GateDecision:
    """Phase 17 gate evaluation for a public chat request.

    Runs Phase 15 NLP → Phase 16 Smart Router → Phase 17 policy check.
    Returns a GateDecision with a structured audit payload.

    This function:
      - Produces a policy decision (allowed / blocked).
      - Does NOT execute any capability.
      - Does NOT write to any database.
      - Does NOT make any network call.
      - Does NOT short-circuit the existing PublicChatRoutingService.

    Args:
        request_text: The raw public chat message text.
        caller_context: Fixed to "public_chat" for all Phase 17 evaluations.
        user_role: Fixed to "none" for unauthenticated public chat users.

    Returns:
        A frozen GateDecision with observability audit_payload populated.
    """
    # Phase 15 — NLP classification
    nlp_result: NLPResult = process_text(request_text)

    # Phase 16 — Capability routing decision
    routing_decision: RoutingDecision = route_capability(
        request_text,
        caller_context=caller_context,
        user_role=user_role,
    )

    # Phase 17 — Gate policy evaluation
    allowed, denial_reason = _evaluate_gate_policy(nlp_result, routing_decision)

    # Build plain-dict audit payload (JSON-safe — no frozen dataclass objects)
    audit_payload: dict[str, Any] = {
        "phase": "17",
        "gate": "public_capability_gate",
        "nlp_trace": build_nlp_trace(nlp_result),
        "routing_trace": build_routing_trace(routing_decision),
        "gate_decision": build_gate_decided_payload(
            allowed=allowed,
            denial_reason=denial_reason,
            routing_decision=routing_decision,
        ),
    }

    return GateDecision(
        allowed=allowed,
        routing_decision=routing_decision,
        nlp_result=nlp_result,
        denial_reason=denial_reason,
        audit_payload=audit_payload,
    )


__all__ = [
    "GateDecision",
    "evaluate_public_capability_gate",
]
