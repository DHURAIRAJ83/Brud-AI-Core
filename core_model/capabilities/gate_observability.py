"""Phase 17: Gate Observability — Plain-Dict Audit Payload Builders.

Converts Phase 15 NLPResult and Phase 16 RoutingDecision into plain,
JSON-serializable Python dicts. No frozen dataclass objects are ever
stored inside an audit payload.

Design constraints:
  ✅ Returns only plain dicts, lists, strings, ints, floats, bools, None.
  ✅ All values are JSON-serializable (no dataclasses, no sets, no tuples
     that would survive json.dumps without a custom encoder).
  ❌ No logging side-effects in this module (callers decide where to emit).
  ❌ No database reads or writes.
  ❌ No network calls.
  ❌ No eval / exec.
"""

from __future__ import annotations

from typing import Any

from core_model.capabilities.smart_router import RoutingDecision
from core_model.nlp.text_processor import NLPResult


def build_nlp_trace(nlp_result: NLPResult) -> dict[str, Any]:
    """Serialize a Phase 15 NLPResult to a plain JSON-safe dict.

    Tuples are converted to lists so json.dumps() works without a custom
    encoder.  The original NLPResult object is never mutated.
    """
    return {
        "detected_language": nlp_result.detected_language,
        "language_confidence": nlp_result.language_confidence,
        "is_tanglish": nlp_result.is_tanglish,
        "is_mixed_language": nlp_result.is_mixed_language,
        "is_technical_code": nlp_result.is_technical_code,
        "normalization_applied": nlp_result.normalization_applied,
        "normalization_notes": list(nlp_result.normalization_notes),
        "nlp_normalization_version": nlp_result.nlp_normalization_version,
        # Exclude original_text / normalized_text / tokens to avoid PII/size.
        # If forensic tracing is needed, callers should pass the input_hash.
    }


def build_routing_trace(routing_decision: RoutingDecision) -> dict[str, Any]:
    """Serialize a Phase 16 RoutingDecision to a plain JSON-safe dict.

    Tuples become lists; None values are kept as-is (JSON null).
    The routing_reason string may contain the full capability id.
    """
    return {
        "selected_capability_id": routing_decision.selected_capability_id,
        "selected_component": routing_decision.selected_component,
        "confidence": routing_decision.confidence,
        "routing_reason": routing_decision.routing_reason,
        "alternative_capabilities": list(routing_decision.alternative_capabilities),
        "access_level_required": routing_decision.access_level_required,
        "requires_human_approval": routing_decision.requires_human_approval,
        "risk_level": routing_decision.risk_level,
        "executable": routing_decision.executable,
        "blocking_reasons": list(routing_decision.blocking_reasons),
        "warnings": list(routing_decision.warnings),
    }


def build_gate_decided_payload(
    *,
    allowed: bool,
    denial_reason: str | None,
    routing_decision: RoutingDecision,
) -> dict[str, Any]:
    """Build the gate-verdict section of the audit payload.

    Contains only the gate's own verdict fields — not a re-dump of the
    full routing trace (which is already in build_routing_trace()).
    """
    return {
        "allowed": allowed,
        "denial_reason": denial_reason,
        "capability_id": routing_decision.selected_capability_id,
        "risk_level": routing_decision.risk_level,
        "requires_human_approval": routing_decision.requires_human_approval,
        "routing_executable": routing_decision.executable,
    }


__all__ = [
    "build_gate_decided_payload",
    "build_nlp_trace",
    "build_routing_trace",
]
