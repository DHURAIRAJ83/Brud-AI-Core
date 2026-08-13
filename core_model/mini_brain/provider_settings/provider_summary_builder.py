"""MB-27: Provider Summary Builder -- pure composition root for the
`GET /providers/{id}` response shape. Assembles masked secrets, health,
and capability flags -- all inputs are pre-fetched by the service;
this module touches no I/O itself.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.provider_settings.provider_capability_matrix import capabilities_for
from core_model.mini_brain.provider_settings.provider_health_summary import summarize
from core_model.mini_brain.provider_settings.secret_masker import mask_secret_list


def build(
    *,
    setting_row: dict[str, Any],
    secret_rows: list[dict[str, Any]],
    last_test_status: str | None = None,
) -> dict[str, Any]:
    provider_key = setting_row["provider_key"]
    present_secret_names = [row["secret_name"] for row in secret_rows]
    health = summarize(
        provider_key=provider_key, enabled=bool(setting_row["enabled"]),
        present_secret_names=present_secret_names, last_test_status=last_test_status,
    )
    return {
        "public_id": setting_row["public_id"],
        "provider_key": provider_key,
        "provider_type": setting_row["provider_type"],
        "enabled": bool(setting_row["enabled"]),
        "config": setting_row.get("config", {}),
        "secrets": mask_secret_list(secret_rows),
        "capability_flags": capabilities_for(provider_key),
        "health": health["health"],
        "updated_at": setting_row.get("updated_at"),
    }
