"""MB-28: Conversation Title Builder -- pure. First-message text to a
short, sanitized session title. No LLM involved.
"""

from __future__ import annotations

_MAX_TITLE_LENGTH = 60


def build_title(*, first_message: str) -> str:
    collapsed = " ".join(first_message.split())
    if not collapsed:
        return "New conversation"
    if len(collapsed) <= _MAX_TITLE_LENGTH:
        return collapsed
    return collapsed[: _MAX_TITLE_LENGTH - 1].rstrip() + "…"
