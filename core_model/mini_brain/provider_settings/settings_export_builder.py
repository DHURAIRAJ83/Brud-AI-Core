"""MB-27: Settings Export Builder -- pure. Builds the export payload
from provider SETTING rows only -- this function's signature never
accepts secret rows as an input at all, so `encrypted_value` cannot
appear in its output by construction, not merely by a masking step
that could later be forgotten.
"""

from __future__ import annotations

from typing import Any

_EXPORT_FIELDS = ("provider_key", "provider_type", "enabled", "config", "updated_at")


def build(setting_rows: list[dict[str, Any]]) -> dict[str, Any]:
    providers = []
    for row in setting_rows:
        providers.append({field: row.get(field) for field in _EXPORT_FIELDS})
    return {"providers": providers}
