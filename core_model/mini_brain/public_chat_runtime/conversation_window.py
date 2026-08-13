"""MB-23: Conversation Window -- pure. Bounds an already-fetched
message list to the most recent N entries -- the service layer is
responsible for querying with a `LIMIT`, never loading full message
history; this module only re-confirms the bound and reports whether
truncation occurred, so the boundary is enforced in one place rather
than trusted implicitly at every call site.
"""

from __future__ import annotations

from typing import Any

DEFAULT_WINDOW_SIZE = 20
MAX_MESSAGE_CHARACTERS = 4_000


def bound_window(*, messages: list[dict[str, Any]], window_size: int = DEFAULT_WINDOW_SIZE) -> dict[str, Any]:
    if window_size <= 0:
        raise ValueError("window_size must be positive")
    truncated = len(messages) > window_size
    windowed = messages[-window_size:] if truncated else list(messages)
    return {
        "messages": windowed, "window_size": window_size, "truncated": truncated,
        "total_available": len(messages), "returned_count": len(windowed),
    }


def cap_message_size(*, text: str, max_characters: int = MAX_MESSAGE_CHARACTERS) -> dict[str, Any]:
    if len(text) <= max_characters:
        return {"text": text, "capped": False, "original_length": len(text)}
    return {"text": text[:max_characters], "capped": True, "original_length": len(text)}
