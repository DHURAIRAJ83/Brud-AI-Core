"""MB-10: Provider Registry -- pure. Validates a requested provider
selection against an already-fetched list of active registry entries
(the real source of truth is the
`mini_brain_research_provider_registry` database table, seeded with
five defaults by the schema migration itself and admin-extensible at
runtime -- never a hardcoded Python enum). This module never reads the
table itself; the service layer does that and passes the rows in.

`DEFAULT_PROVIDER_KEYS` mirrors the migration's own seed data purely
for documentation and test fixtures -- it is not consulted at runtime
by the service, which always defers to the real, possibly
admin-extended table.
"""

from __future__ import annotations

from typing import Any

DEFAULT_PROVIDER_KEYS = ("claude", "openai", "gemini", "openrouter", "local_model")


def select_providers(
    *, requested_provider_keys: list[str], registered_providers: list[dict[str, Any]],
) -> dict[str, Any]:
    active_by_key = {p["provider_key"]: p for p in registered_providers if p["status"] == "active"}
    selected = []
    unknown = []
    for key in requested_provider_keys:
        if key in active_by_key:
            selected.append(active_by_key[key])
        else:
            unknown.append(key)
    return {
        "selected_providers": selected,
        "unknown_provider_keys": unknown,
        "valid": bool(selected) and not unknown,
    }
