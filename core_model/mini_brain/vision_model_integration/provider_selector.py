"""MB-15: Provider Selection -- pure. Validates a requested provider
against the registry's own real rows (never hardcodes a provider) and
against which backend implementations actually exist. Never assumes a
provider is usable just because its registry row is 'active' -- that
only means an admin has not disabled it; whether it is truly available
is a separate, live check the service performs against the real
backend.
"""

from __future__ import annotations

from typing import Any


def select_provider(
    *, provider_key: str, registry_rows: list[dict[str, Any]], implemented_provider_keys: set[str],
) -> dict[str, Any]:
    matching = [row for row in registry_rows if row["provider_key"] == provider_key]
    if not matching:
        return {
            "selected": False, "provider_key": provider_key,
            "reason": f"'{provider_key}' is not a registered provider",
        }
    row = matching[0]
    if row["status"] != "active":
        return {
            "selected": False, "provider_key": provider_key,
            "reason": f"provider '{provider_key}' is disabled by an admin (status={row['status']!r})",
        }
    if provider_key not in implemented_provider_keys:
        return {
            "selected": False, "provider_key": provider_key,
            "reason": f"provider '{provider_key}' is a registered future placeholder with no backend implementation yet",
        }
    return {
        "selected": True, "provider_key": provider_key, "display_name": row["display_name"],
        "backend_type": row["backend_type"], "hardware_target": row["hardware_target"],
    }
