"""MB-30: Runtime State Builder -- pure. Assembles the `/status`
response shape from already-fetched data (current runtime row,
installations list, hardware summary) -- never fetches any of it
itself.
"""

from __future__ import annotations

from typing import Any


def build_status(
    *, current_runtime: dict[str, Any] | None, installations: list[dict[str, Any]], hardware: dict[str, Any] | None,
) -> dict[str, Any]:
    installed = [item for item in installations if item.get("status") == "installed"]
    return {
        "loaded": bool(current_runtime and current_runtime.get("loaded")),
        "current_model": current_runtime,
        "installed_count": len(installed),
        "installed_models": installed,
        "hardware": hardware,
    }
