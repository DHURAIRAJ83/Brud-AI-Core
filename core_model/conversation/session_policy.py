"""Conversation memory policy validation and session-mode capability
resolution.

A policy controls what a session is *allowed* to do; it never forces a
weaker mode to behave as a stronger one. ``private_no_persist`` and
``stateless`` always structurally disable persistence, regardless of a
policy's other flags -- a policy can restrict further, never loosen
these two modes' hard guarantees.
"""

from __future__ import annotations

from typing import Any

from core_model.conversation import (
    FORBIDDEN_MEMORY_CATEGORIES,
    MEMORY_CATEGORIES,
    SESSION_MODES,
)


def validate_policy_limits(payload: dict[str, Any]) -> list[str]:
    """Returns a list of validation error strings; empty means valid."""

    errors: list[str] = []
    if payload.get("default_session_mode") not in SESSION_MODES:
        errors.append("default_session_mode must be one of the supported session modes")
    for field_name in (
        "maximum_session_turns",
        "maximum_session_age_seconds",
        "maximum_short_term_tokens",
        "maximum_summary_tokens",
        "maximum_memory_items",
        "default_memory_ttl_seconds",
    ):
        value = payload.get(field_name)
        if value is not None and value <= 0:
            errors.append(f"{field_name} must be a positive integer")
    allowed_categories = payload.get("allowed_memory_categories", [])
    for category in allowed_categories:
        if category not in MEMORY_CATEGORIES:
            errors.append(f"allowed_memory_categories contains unsupported category: {category}")
        if category in FORBIDDEN_MEMORY_CATEGORIES:
            errors.append(
                f"allowed_memory_categories may never include forbidden category: {category}"
            )
    return errors


def session_mode_capabilities(mode: str) -> dict[str, bool]:
    """Structural capability of a session mode, independent of any
    policy's own flags -- a policy can restrict further but never grant
    persistence back to a mode that structurally forbids it."""

    if mode == "stateless":
        return {
            "persist_turns": False, "allow_summary": False, "allow_long_term_memory": False,
        }
    if mode == "private_no_persist":
        return {
            "persist_turns": False, "allow_summary": False, "allow_long_term_memory": False,
        }
    if mode == "session_memory":
        return {
            "persist_turns": True, "allow_summary": True, "allow_long_term_memory": False,
        }
    if mode == "consented_memory":
        return {
            "persist_turns": True, "allow_summary": True, "allow_long_term_memory": True,
        }
    raise ValueError(f"unsupported session mode: {mode}")


def resolve_effective_capabilities(mode: str, policy: dict[str, Any]) -> dict[str, bool]:
    """Intersects the mode's structural capability with the policy's own
    allow_* flags -- the policy may only restrict, never loosen."""

    structural = session_mode_capabilities(mode)
    return {
        "persist_turns": (
            structural["persist_turns"]
            and bool(policy.get("allow_short_term_context", True))
        ),
        "allow_summary": (
            structural["allow_summary"]
            and bool(policy.get("allow_session_summary", True))
        ),
        "allow_long_term_memory": (
            structural["allow_long_term_memory"]
            and bool(policy.get("allow_long_term_memory", False))
        ),
    }
