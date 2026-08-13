"""Configuration defaults and validation for the Mini Brain skeleton.

MB-01 configuration is deliberately small: it governs the framework
(logging verbosity, whether placeholder interfaces are reachable),
never a model (there is none yet). `runtime_backend` is fixed to
`"none"` in this phase and is structurally rejected if set to
anything else -- future phases add new allowed values here, not a
rewrite of this validator.
"""

from __future__ import annotations

from typing import Any

LOG_LEVELS = ("debug", "info", "warning", "error")

# The only backend value MB-01 permits. Explicitly not "ollama" --
# see MB-01's own requirement that the runtime must not depend on
# Ollama, and must instead be ready for a future CPU-only local model.
ALLOWED_RUNTIME_BACKENDS = ("none",)

DEFAULT_CONFIG: dict[str, Any] = {
    "log_level": "info",
    "runtime_backend": "none",
    "placeholder_interfaces_enabled": True,
}


def validate_config(config: dict[str, Any]) -> list[str]:
    """Returns a list of validation issue strings; empty means valid."""

    issues: list[str] = []
    if config.get("log_level") not in LOG_LEVELS:
        issues.append("log_level must be one of: " + ", ".join(LOG_LEVELS))
    if config.get("runtime_backend") not in ALLOWED_RUNTIME_BACKENDS:
        issues.append(
            "runtime_backend must be one of: " + ", ".join(ALLOWED_RUNTIME_BACKENDS)
            + " (MB-01 ships no model backend)"
        )
    if not isinstance(config.get("placeholder_interfaces_enabled"), bool):
        issues.append("placeholder_interfaces_enabled must be a boolean")
    return issues
