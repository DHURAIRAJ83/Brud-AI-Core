"""MB-25: Public Chat Runtime Guard -- pure. Reuses MB-24's own
`permission_scope_registry.is_public_chat_available()` directly --
never a second sensitivity table -- to decide whether a public-chat
caller may execute a given plugin at all for a given scope.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.plugin_governance.permission_scope_registry import is_public_chat_available


def evaluate_public_chat_execution(*, public_chat_enabled: bool, required_scope: str) -> dict[str, Any]:
    if not public_chat_enabled:
        return {"allowed": False, "reason": "plugin is not enabled for public chat"}
    if not is_public_chat_available(required_scope):
        return {"allowed": False, "reason": f"scope '{required_scope}' is not available to public chat"}
    return {"allowed": True, "reason": None}
