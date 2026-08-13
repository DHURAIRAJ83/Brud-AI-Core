"""Runtime state machine -- the 6 states MB-04 requires, plus their
valid transitions. Same shape as MB-01's own `status.py`, extended for
a real (if not-yet-provisioned) model lifecycle: Unloaded, Loading,
Loaded, Running, Error, Unloading.
"""

from __future__ import annotations

RUNTIME_STATES = ("unloaded", "loading", "loaded", "running", "error", "unloading")

_ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "unloaded": ("loading",),
    "loading": ("loaded", "error"),
    "loaded": ("running", "unloading", "error"),
    "running": ("loaded", "error"),
    "error": ("loading", "unloading", "unloaded"),
    "unloading": ("unloaded", "error"),
}


def is_valid_transition(from_state: str, to_state: str) -> bool:
    if from_state not in RUNTIME_STATES or to_state not in RUNTIME_STATES:
        return False
    return to_state in _ALLOWED_TRANSITIONS.get(from_state, ())


def can_generate(state: str) -> bool:
    """Only a model that finished loading and isn't mid-generation
    already may accept a new generation request."""

    return state == "loaded"


def can_load(state: str) -> bool:
    return state in ("unloaded", "error")


def can_unload(state: str) -> bool:
    return state in ("loaded", "error")
