"""MB-28: Tool Intent Classifier -- pure. Keyword/pattern classifier
that decides whether an admin's message calls for a read-only tool
call or a plain reply. `candidate_scope_key` is always one of MB-24's
`core_model.mini_brain.plugin_governance.permission_scope_registry.
known_scopes()` -- this module imports only that registry's read-only
accessor, never an execution function.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.plugin_governance.permission_scope_registry import known_scopes

_KEYWORD_TO_SCOPE: dict[str, str] = {
    "this conversation": "chat.read.current",
    "current chat": "chat.read.current",
    "chat history": "chat.read.history",
    "past conversation": "chat.read.history",
    "calendar": "calendar.read",
    "send an email": "email.send",
    "send email": "email.send",
    "clipboard": "clipboard.read",
}

_LOW_CONFIDENCE_THRESHOLD = 0.35


def classify(*, message: str) -> dict[str, Any]:
    lowered = message.lower()
    known = set(known_scopes())

    best_scope: str | None = None
    best_score = 0.0
    for keyword, scope_key in _KEYWORD_TO_SCOPE.items():
        if keyword in lowered and scope_key in known:
            score = 0.6 + (0.1 * lowered.count(keyword))
            if score > best_score:
                best_score = score
                best_scope = scope_key

    if best_scope is None:
        return {"intent": "plain_reply", "candidate_scope_key": None, "confidence": 1.0 if message.strip() else 0.0}

    intent = "tool_call" if best_score >= _LOW_CONFIDENCE_THRESHOLD else "plain_reply"
    return {"intent": intent, "candidate_scope_key": best_scope, "confidence": min(best_score, 1.0)}
