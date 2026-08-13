"""MB-24: Sandbox Profile Builder -- pure. Builds the task spec's own
Step 10 sandbox profile shape from a plugin's already-classified
scopes -- governance metadata only. No real sandbox process, container,
or OS-level isolation is created anywhere in this phase.
"""

from __future__ import annotations

from typing import Any

DEFAULT_MEMORY_LIMIT_MB = 256
ELEVATED_MEMORY_LIMIT_MB = 512
DEFAULT_CPU_TIME_LIMIT_MS = 5_000
_ELEVATED_RISK_LEVELS = frozenset({"high", "critical"})


def build_sandbox_profile(
    *, requested_scopes: list[str], allowed_domains: list[str], filesystem_roots: list[str],
    risk_level: str = "low",
) -> dict[str, Any]:
    network_enabled = "network.http.allowed_domains" in requested_scopes
    clipboard_access = any(scope.startswith("clipboard.") for scope in requested_scopes)
    camera_access = "camera.capture" in requested_scopes
    microphone_access = "microphone.capture" in requested_scopes
    persistent_storage = any(scope.startswith("plugin.storage.") for scope in requested_scopes)
    memory_limit_mb = ELEVATED_MEMORY_LIMIT_MB if risk_level in _ELEVATED_RISK_LEVELS else DEFAULT_MEMORY_LIMIT_MB

    return {
        "network_enabled": network_enabled, "allowed_domains": list(allowed_domains) if network_enabled else [],
        "filesystem_roots": list(filesystem_roots), "memory_limit_mb": memory_limit_mb,
        "cpu_time_limit_ms": DEFAULT_CPU_TIME_LIMIT_MS,
        "background_execution": False,
        "persistent_storage": persistent_storage, "clipboard_access": clipboard_access,
        "camera_access": camera_access, "microphone_access": microphone_access,
        "disclosure": (
            "governance metadata only -- no real sandbox execution, container, or OS-level isolation "
            "exists anywhere in this phase; background_execution is always False since no runtime can "
            "honor it yet"
        ),
    }
