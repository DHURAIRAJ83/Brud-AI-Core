"""Deterministic fallback resolution.

The runtime never retries indefinitely, never loads an unapproved model,
and never silently switches to an unrelated model — a requested
``previous_active_assignment`` fallback with no available previous
version degrades safely to ``placeholder`` rather than failing open.
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.inference_runtime import FALLBACK_POLICIES


@dataclass(frozen=True)
class FallbackDecision:
    action: str
    reason: str


def decide_fallback(
    policy: str, *, previous_assignment_version_available: bool
) -> FallbackDecision:
    if policy not in FALLBACK_POLICIES:
        raise ValueError(f"fallback policy must be one of {FALLBACK_POLICIES}")
    if policy == "previous_active_assignment" and not previous_assignment_version_available:
        return FallbackDecision(
            action="placeholder",
            reason="no previous assignment version available, defaulting to placeholder",
        )
    return FallbackDecision(action=policy, reason=f"configured fallback policy: {policy}")


def build_fallback_event(
    *, assignment_public_id: str, decision: FallbackDecision, failure_code: str
) -> dict[str, str]:
    return {
        "assignment_public_id": assignment_public_id,
        "fallback_action": decision.action,
        "reason": decision.reason,
        "failure_code": failure_code,
    }
