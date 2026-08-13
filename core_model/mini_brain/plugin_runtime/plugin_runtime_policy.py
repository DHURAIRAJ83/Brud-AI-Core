"""MB-25: Plugin Runtime Policy -- pure. The single top-level gate the
service calls immediately before Stage 9 "Execute Plugin": combines
the plugin's own enabled status with the already-computed permission
gate, consent gate, and mode guard (public-chat or Admin Assistant)
results into one `may_execute` decision with every contributing
reason. This never re-derives any of those sub-decisions itself.
"""

from __future__ import annotations

from typing import Any


def evaluate_execution_policy(
    *, plugin_status: str, permission_result: dict[str, Any], consent_result: dict[str, Any],
    mode_guard_result: dict[str, Any],
) -> dict[str, Any]:
    if plugin_status != "enabled":
        return {"may_execute": False, "reasons": [f"plugin status is '{plugin_status}', not 'enabled'"]}

    reasons: list[str] = []
    if not mode_guard_result["allowed"]:
        reasons.append(mode_guard_result["reason"])
    if not permission_result["allowed"]:
        reasons.append(permission_result["reason"])
    if not consent_result["allowed"]:
        reasons.append(consent_result["reason"])

    return {"may_execute": not reasons, "reasons": reasons}
