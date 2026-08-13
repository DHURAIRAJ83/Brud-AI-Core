"""MB-27: Diagnostics Builder -- pure. Assembles the `GET /diagnostics`
response payload from already-computed inputs. Takes no I/O itself --
the service gathers live counts/probe results and calls this function
with them.
"""

from __future__ import annotations

from typing import Any


def build(
    *,
    encryption_available: bool,
    configured_provider_count: int,
    enabled_provider_count: int,
    provider_health: list[dict[str, Any]],
    unavailable_providers: list[str],
) -> dict[str, Any]:
    return {
        "encryption_available": encryption_available,
        "missing_encryption_key": not encryption_available,
        "configured_provider_count": configured_provider_count,
        "enabled_provider_count": enabled_provider_count,
        "provider_health": provider_health,
        "unavailable_providers": unavailable_providers,
    }
