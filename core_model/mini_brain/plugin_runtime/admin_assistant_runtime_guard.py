"""MB-25: Admin Assistant Runtime Guard -- pure. Admin Assistant is
not a bypass: this module requires both `admin_assistant_enabled` on
the plugin's own manifest and a genuinely authorized admin identity --
never one without the other.
"""

from __future__ import annotations

from typing import Any


def evaluate_admin_assistant_execution(*, admin_assistant_enabled: bool, admin_authorized: bool) -> dict[str, Any]:
    if not admin_assistant_enabled:
        return {"allowed": False, "reason": "plugin is not enabled for Admin Assistant"}
    if not admin_authorized:
        return {
            "allowed": False,
            "reason": "Admin Assistant execution requires a real, authorized admin identity -- Admin Assistant is not a bypass",
        }
    return {"allowed": True, "reason": None}
