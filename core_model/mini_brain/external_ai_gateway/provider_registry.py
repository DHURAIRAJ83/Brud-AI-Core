"""MB-21: Provider Registry -- pure. Validates a requested provider
selection against an already-determined list of provider availability
facts (the service layer determines real availability by asking each
provider client's own `is_available()`; this module never makes that
determination itself). Mirrors MB-10's own `research_center.
provider_registry.select_providers()` structurally -- never a
hardcoded Python enum of "the" providers, since the real source of
truth is always the service's own live client instances.
"""

from __future__ import annotations

from typing import Any

KNOWN_PROVIDER_KEYS = ("openrouter",)
PROVIDER_STATUSES = ("enabled", "disabled", "rate_limited", "unavailable")


def select_providers(
    *, requested_provider_keys: list[str], provider_availability: list[dict[str, Any]],
) -> dict[str, Any]:
    """`provider_availability`: one entry per known provider, each
    ``{"provider_key": str, "status": "enabled"|"disabled"|"rate_limited"|"unavailable"}``,
    already determined by the service layer."""
    by_key = {p["provider_key"]: p for p in provider_availability}
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    unknown: list[str] = []

    for key in requested_provider_keys:
        entry = by_key.get(key)
        if entry is None:
            unknown.append(key)
        elif entry["status"] == "enabled":
            selected.append(entry)
        else:
            skipped.append(entry)

    return {
        "selected_providers": selected, "skipped_providers": skipped, "unknown_provider_keys": unknown,
        "selected_count": len(selected), "ready": len(selected) > 0,
        "disclosure": (
            "provider status is determined live by the service layer asking each provider client's "
            "own is_available() -- never a cached or assumed value"
        ),
    }
