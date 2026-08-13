"""MB-24: Plugin Capability Classifier -- pure. Groups a plugin's own
requested scopes into coarse capability categories and a sensitivity
breakdown, using only the fixed permission scope registry -- never
plugin code inspection, since no plugin code is ever executed or
parsed by this phase.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.plugin_governance.permission_scope_registry import scope_definition

_CATEGORY_BY_SCOPE_PREFIX: tuple[tuple[str, str], ...] = (
    ("chat.", "chat_access"),
    ("filesystem.", "filesystem_access"),
    ("network.", "network_access"),
    ("image.", "media_generation"),
    ("calendar.", "calendar_access"),
    ("email.", "communication"),
    ("clipboard.", "clipboard_access"),
    ("microphone.", "sensory_capture"),
    ("camera.", "sensory_capture"),
    ("plugin.storage.", "storage_access"),
    ("admin.", "admin_capability"),
)


def classify_capabilities(*, requested_scopes: list[str]) -> dict[str, Any]:
    categories: set[str] = set()
    sensitivity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    unknown_scopes: list[str] = []

    for scope in requested_scopes:
        definition = scope_definition(scope)
        if definition is None:
            unknown_scopes.append(scope)
            continue
        sensitivity_counts[definition["sensitivity"]] += 1
        for prefix, category in _CATEGORY_BY_SCOPE_PREFIX:
            if scope.startswith(prefix):
                categories.add(category)
                break

    return {
        "capability_categories": sorted(categories), "sensitivity_counts": sensitivity_counts,
        "unknown_scopes": unknown_scopes,
        "requests_high_or_critical_scope": sensitivity_counts["high"] > 0 or sensitivity_counts["critical"] > 0,
        "disclosure": "derived entirely from the fixed permission scope registry -- never plugin code inspection, since no plugin code is executed by this phase",
    }
