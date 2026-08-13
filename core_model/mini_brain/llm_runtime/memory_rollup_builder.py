"""MB-28: Memory Rollup Builder -- pure. Session aggregate counts to
the exact `mini_brain_llm_runtime_memory` row shape.
"""

from __future__ import annotations

from typing import Any

_VALID_EVENT_TYPES = frozenset(
    {
        "session_started",
        "reply_generated",
        "tool_call_dispatched",
        "fallback_to_external",
        "session_closed",
        "session_deleted",
    }
)


def build_memory_row(
    *,
    session_public_id: str,
    admin_public_id: str,
    event_type: str,
    backend_type: str | None,
    total_messages: int,
) -> dict[str, Any]:
    if event_type not in _VALID_EVENT_TYPES:
        raise ValueError(f"unknown memory event_type: {event_type}")
    return {
        "session_id": session_public_id,
        "admin_public_id": admin_public_id,
        "event_type": event_type,
        "backend_type": backend_type,
        "total_messages": total_messages,
    }
