"""MB-25: Execution Context Builder -- pure. Builds the metadata-only
`context` dict passed to a plugin's own `run(context, arguments)`
entrypoint. Never includes a raw execution token, an admin identity,
or a filesystem/network handle -- any guarded access a plugin needs
must come through the service layer's own separately-injected,
guard-checked helper callables, never through this static dict.
"""

from __future__ import annotations

from typing import Any


def build_execution_context(
    *, execution_public_id: str, plugin_public_id: str, granted_scopes: list[str],
    memory_limit_mb: int | None, cpu_time_limit_ms: int | None, requester_kind: str, requester_id_hash: str | None,
) -> dict[str, Any]:
    return {
        "execution_id": execution_public_id, "plugin_id": plugin_public_id,
        "granted_scopes": sorted(granted_scopes), "memory_limit_mb": memory_limit_mb,
        "cpu_time_limit_ms": cpu_time_limit_ms, "requester_kind": requester_kind,
        "requester_id_hash": requester_id_hash,
        "disclosure": (
            "context metadata only -- any filesystem or network access a plugin needs must come through "
            "a separately-injected, guard-checked helper the service layer provides, never through a raw "
            "import inside the plugin's own code"
        ),
    }
