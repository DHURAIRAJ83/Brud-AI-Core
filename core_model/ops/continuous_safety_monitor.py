"""Phase 61 - P7: Continuous Safety Monitoring Engine.

Monitors real-time production safety events and produces escalation governance signals.

CRITICAL INVARIANTS:
- Safety states: SAFE | WARNING | VIOLATION | CRITICAL.
- Critical safety violations produce TRAFFIC_FREEZE, ROLLBACK_REQUIRED, or PUBLIC_CHAT_SUSPENDED.
- No direct model mutation or automatic retraining.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SafetyEventRecord:
    """Record of production safety event."""
    event_id: str
    release_id: str
    model_hash: str
    event_type: str  # PROMPT_INJECTION | INSTRUCTION_HIERARCHY | GOVERNANCE_BYPASS | DATA_LEAKAGE | MEMORIZATION | UNQUALIFIED_OUTPUT
    severity: str    # WARNING | VIOLATION | CRITICAL
    description: str
    timestamp: str


@dataclass
class SafetyEvaluationResult:
    """Outcome of continuous safety evaluation."""
    safety_status: str  # SAFE | WARNING | VIOLATION | CRITICAL
    escalation_action: str | None  # TRAFFIC_FREEZE | ROLLBACK_REQUIRED | PUBLIC_CHAT_SUSPENDED | NONE
    event_count: int
    critical_events: list[SafetyEventRecord] = field(default_factory=list)


class ContinuousSafetyMonitor:
    """Continuous production safety monitor."""

    def __init__(self) -> None:
        self._events: list[SafetyEventRecord] = []

    def log_safety_event(
        self,
        release_id: str,
        model_hash: str,
        event_type: str,
        severity: str,
        description: str,
    ) -> SafetyEventRecord:
        """Log an immutable safety event."""
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        event_id = f"safe-evt-{len(self._events)+1:04d}"
        rec = SafetyEventRecord(
            event_id=event_id,
            release_id=release_id,
            model_hash=model_hash,
            event_type=event_type,
            severity=severity,
            description=description,
            timestamp=now
        )
        self._events.append(rec)
        return rec

    def evaluate_safety_status(self, release_id: str) -> SafetyEvaluationResult:
        """Evaluate overall safety status and determine required escalation action."""
        rel_events = [e for e in self._events if e.release_id == release_id]
        if not rel_events:
            return SafetyEvaluationResult(
                safety_status="SAFE",
                escalation_action="NONE",
                event_count=0,
                critical_events=[]
            )

        critical_events = [e for e in rel_events if e.severity == "CRITICAL"]
        violations = [e for e in rel_events if e.severity == "VIOLATION"]

        if critical_events:
            return SafetyEvaluationResult(
                safety_status="CRITICAL",
                escalation_action="ROLLBACK_REQUIRED",
                event_count=len(rel_events),
                critical_events=critical_events
            )

        if len(violations) >= 2:
            return SafetyEvaluationResult(
                safety_status="VIOLATION",
                escalation_action="TRAFFIC_FREEZE",
                event_count=len(rel_events),
                critical_events=violations
            )

        if len(rel_events) > 0:
            return SafetyEvaluationResult(
                safety_status="WARNING",
                escalation_action="NONE",
                event_count=len(rel_events),
                critical_events=[]
            )

        return SafetyEvaluationResult(
            safety_status="SAFE",
            escalation_action="NONE",
            event_count=0,
            critical_events=[]
        )
