"""MB-24: Runtime Policy Evaluator -- pure. This is the task spec's
own Step 2 "Plugin Runtime Permission Engine": given a scope, a
plugin's current status, whether the caller is public chat, whether a
valid consent exists, whether the plugin has passed admin review, and
the plugin's own risk level, deterministically decide one of allow /
deny / require_consent / require_admin_review / disabled, always with
an explicit list of reasons.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.plugin_governance.permission_scope_registry import is_known_scope, scope_definition

_HIGH_RISK_LEVELS = frozenset({"high", "critical"})


def evaluate_permission(
    *, scope_key: str, plugin_status: str, is_public_chat: bool, has_valid_consent: bool,
    admin_reviewed: bool, risk_level: str | None,
) -> dict[str, Any]:
    if not is_known_scope(scope_key):
        return {"decision": "deny", "reasons": [f"unknown scope: {scope_key!r}"], "scope_key": scope_key}

    definition = scope_definition(scope_key)
    reasons: list[str] = []

    if plugin_status == "archived":
        return {"decision": "disabled", "reasons": ["plugin is archived"], "scope_key": scope_key}
    if plugin_status == "disabled":
        return {"decision": "disabled", "reasons": ["plugin is disabled"], "scope_key": scope_key}

    if is_public_chat and not definition["public_chat_available"]:
        return {
            "decision": "deny",
            "reasons": [f"scope '{scope_key}' is not available to public chat (sensitivity={definition['sensitivity']})"],
            "scope_key": scope_key,
        }

    if definition["admin_review_required"] and not admin_reviewed:
        return {
            "decision": "require_admin_review",
            "reasons": [f"scope '{scope_key}' requires admin review before it can ever be granted"],
            "scope_key": scope_key,
        }

    if risk_level in _HIGH_RISK_LEVELS and not admin_reviewed:
        reasons.append(f"plugin risk_level={risk_level!r} requires admin review before any scope can be granted")
        return {"decision": "require_admin_review", "reasons": reasons, "scope_key": scope_key}

    if definition["consent_required"] and not has_valid_consent:
        return {
            "decision": "require_consent", "reasons": [f"scope '{scope_key}' requires valid user consent"],
            "scope_key": scope_key,
        }

    return {"decision": "allow", "reasons": ["all applicable policy checks passed"], "scope_key": scope_key}
