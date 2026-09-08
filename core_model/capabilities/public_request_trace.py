"""Phase 18: Public Request Trace & Lifecycle Observability Schema.

Provides an immutable schema and JSON-serializable trace builder for correlating
and observing the complete Public Chat request lifecycle across:
  request_received -> input_validated -> nlp_processed -> routing_evaluated
  -> gate_evaluated -> service_dispatched -> response_generated -> request_completed (or request_failed)

Critical invariants:
  ✅ Immutable (frozen dataclass).
  ✅ Deterministic (except runtime-generated request_id/timestamp/latency).
  ✅ Contains no secrets, tokens, authorization headers, API keys, or raw full PII.
  ✅ JSON-serializable output via build_public_request_trace().
  ❌ No database reads or writes.
  ❌ No network calls.
  ❌ No subprocess, eval, or exec.
  ❌ No side-effects or background execution.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Sequence
from uuid import uuid4

# Standard lifecycle stages used in Public Chat observability
VALID_TRACE_STAGES: tuple[str, ...] = (
    "request_received",
    "input_validated",
    "nlp_processed",
    "routing_evaluated",
    "gate_evaluated",
    "service_dispatched",
    "response_generated",
    "request_completed",
    "request_failed",
)

# Standard error classifications for request failures
VALID_ERROR_CLASSIFICATIONS: tuple[str, ...] = (
    "none",
    "validation_error",
    "rate_limited",
    "nlp_classification_failed",
    "routing_failed_closed",
    "gate_blocked",
    "rag_unavailable",
    "memory_unavailable",
    "provider_unavailable",
    "timeout",
    "output_blocked",
    "internal_error",
)


@dataclass(frozen=True)
class PublicRequestTrace:
    """Immutable trace metadata object for one Public Chat request lifecycle turn.

    Attributes:
        request_id: Correlation identifier linking all processing stages.
        stage: Current lifecycle stage string.
        timestamp: Unix timestamp when trace was constructed.
        language: Detected language code ("ta", "en", "tanglish", "mixed", "unknown").
        language_confidence: Confidence score of language detection (0.0 to 1.0).
        capability_id: Selected capability identifier or None if unrouted.
        component: Source implementation component or None.
        gate_allowed: Boolean verdict of Phase 17 PublicCapabilityGate or None.
        risk_level: Risk classification ("low", "medium", "high", "critical") or None.
        error_classification: Error taxonomy code or "none".
        latency_ms: Accumulated latency in milliseconds or None.
    """

    request_id: str
    stage: str
    timestamp: float
    language: str
    language_confidence: float
    capability_id: str | None
    component: str | None
    gate_allowed: bool | None
    risk_level: str | None
    error_classification: str | None
    latency_ms: float | None

    def __post_init__(self) -> None:
        if self.stage not in VALID_TRACE_STAGES:
            raise ValueError(f"Invalid trace stage {self.stage!r}")
        if self.error_classification is not None and self.error_classification not in VALID_ERROR_CLASSIFICATIONS:
            raise ValueError(f"Invalid error_classification {self.error_classification!r}")


def generate_request_id() -> str:
    """Generate a standard correlation UUID string if none exists."""
    return str(uuid4())


def build_public_request_trace(
    *,
    request_id: str | None = None,
    stage: str = "request_received",
    timestamp: float | None = None,
    language: str = "unknown",
    language_confidence: float = 0.0,
    capability_id: str | None = None,
    component: str | None = None,
    gate_allowed: bool | None = None,
    risk_level: str | None = None,
    error_classification: str | None = "none",
    latency_ms: float | None = None,
    knowledge_gap_detected: bool = False,
    gap_type: str | None = None,
    gap_severity: str | None = None,
    clarification_required: bool = False,
    clarification_reason: str | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct a plain, JSON-serializable dictionary representation of a PublicRequestTrace.

    Converts all tuples/sets/dataclasses to plain python dicts and lists. Sanitizes any secret
    or credential keys if provided in extra_metadata.

    Args:
        request_id: Unique correlation ID. Generated automatically if None.
        stage: One of VALID_TRACE_STAGES.
        timestamp: Epoch timestamp. Defaults to time.time().
        language: Detected language code.
        language_confidence: Language detection confidence (0.0 to 1.0).
        capability_id: Selected capability ID.
        component: Selected source component.
        gate_allowed: Gate policy decision bool.
        risk_level: Risk level string.
        error_classification: One of VALID_ERROR_CLASSIFICATIONS.
        latency_ms: Latency measurement in ms.
        knowledge_gap_detected: Optional Phase 19 boolean flag.
        gap_type: Optional Phase 19 gap taxonomy string code.
        gap_severity: Optional Phase 19 severity string.
        clarification_required: Optional Phase 19 clarification requirement bool.
        clarification_reason: Optional Phase 19 clarification reason string.
        extra_metadata: Optional dict of safe auxiliary metadata.

    Returns:
        A plain dict ready for logging or JSON serialization.
    """
    resolved_id = request_id or generate_request_id()
    resolved_ts = timestamp if timestamp is not None else round(time.time(), 3)
    resolved_stage = stage if stage in VALID_TRACE_STAGES else "request_received"
    resolved_err = error_classification if error_classification in VALID_ERROR_CLASSIFICATIONS else "none"

    trace_obj = PublicRequestTrace(
        request_id=resolved_id,
        stage=resolved_stage,
        timestamp=resolved_ts,
        language=language,
        language_confidence=round(float(language_confidence), 2),
        capability_id=capability_id,
        component=component,
        gate_allowed=gate_allowed,
        risk_level=risk_level,
        error_classification=resolved_err,
        latency_ms=round(float(latency_ms), 2) if latency_ms is not None else None,
    )

    result: dict[str, Any] = {
        "phase": "18",
        "trace_type": "public_request_trace",
        "request_id": trace_obj.request_id,
        "stage": trace_obj.stage,
        "timestamp": trace_obj.timestamp,
        "language": trace_obj.language,
        "language_confidence": trace_obj.language_confidence,
        "capability_id": trace_obj.capability_id,
        "component": trace_obj.component,
        "gate_allowed": trace_obj.gate_allowed,
        "risk_level": trace_obj.risk_level,
        "error_classification": trace_obj.error_classification,
        "latency_ms": trace_obj.latency_ms,
        "knowledge_gap_detected": knowledge_gap_detected,
        "gap_type": gap_type,
        "gap_severity": gap_severity,
        "clarification_required": clarification_required,
        "clarification_reason": clarification_reason,
    }

    if extra_metadata is not None and isinstance(extra_metadata, dict):
        sanitized_extra: dict[str, Any] = {}
        for k, v in extra_metadata.items():
            # Exclude forbidden credential / header keys
            k_low = str(k).lower()
            if any(secret_kw in k_low for secret_kw in ("api_key", "secret", "token", "password", "auth", "bearer")):
                continue
            if isinstance(v, (set, tuple)):
                sanitized_extra[str(k)] = list(v)
            elif isinstance(v, (str, int, float, bool, type(None))):
                sanitized_extra[str(k)] = v
            elif isinstance(v, dict):
                sanitized_extra[str(k)] = {str(dk): str(dv) for dk, dv in v.items()}
            else:
                sanitized_extra[str(k)] = str(v)
        if sanitized_extra:
            result["metadata"] = sanitized_extra

    return result


__all__ = [
    "PublicRequestTrace",
    "VALID_ERROR_CLASSIFICATIONS",
    "VALID_TRACE_STAGES",
    "build_public_request_trace",
    "generate_request_id",
]
