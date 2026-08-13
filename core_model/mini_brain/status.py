"""Runtime status state machine for the Mini Brain skeleton.

MB-01 has no model to actually run, so "runtime status" describes the
*framework's* lifecycle state, not inference readiness. Kept as an
explicit, small state machine (rather than free-form strings) so a
future phase that adds real model loading can reuse these exact
states and transition rules unchanged.
"""

from __future__ import annotations

RUNTIME_STATUSES = ("stopped", "starting", "running", "stopping", "error")

# (from_status -> allowed to_statuses). Anything not listed here is a
# rejected transition, including e.g. "stopped" -> "stopped" (no-op
# transitions have to go through the caller's own idempotency check,
# not silently succeed here).
_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "stopped": ("starting",),
    "starting": ("running", "error"),
    "running": ("stopping", "error"),
    "stopping": ("stopped", "error"),
    "error": ("starting", "stopped"),
}


def is_valid_transition(from_status: str, to_status: str) -> bool:
    if from_status not in RUNTIME_STATUSES or to_status not in RUNTIME_STATUSES:
        return False
    return to_status in _ALLOWED_TRANSITIONS.get(from_status, ())


def decide_health(*, enabled: bool, runtime_status: str, config_valid: bool) -> dict[str, object]:
    """Framework-only health decision -- there is no model to probe in
    MB-01, so "healthy" means exactly: the module is enabled, its
    runtime reached `running` cleanly, and its stored configuration is
    structurally valid. Never reports healthy by default/omission."""

    if not config_valid:
        return {"status": "unhealthy", "reason": "invalid_configuration"}
    if not enabled:
        return {"status": "disabled", "reason": "module_disabled"}
    if runtime_status == "running":
        return {"status": "healthy", "reason": "runtime_running"}
    if runtime_status == "error":
        return {"status": "unhealthy", "reason": "runtime_error"}
    return {"status": "degraded", "reason": f"runtime_{runtime_status}"}
