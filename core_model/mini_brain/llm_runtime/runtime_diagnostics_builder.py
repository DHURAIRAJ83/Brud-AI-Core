"""MB-28: Runtime Diagnostics Builder -- pure. Assembles the
diagnostics response shape from pre-computed inputs, so it is
unit-testable without a real adapter. `configured_model_path` is
always the filename only -- never the full absolute path -- so no
diagnostics response ever leaks filesystem layout.
"""

from __future__ import annotations

from typing import Any


def mask_model_path(model_path: str | None) -> str | None:
    if not model_path:
        return None
    return model_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]


def build_diagnostics(
    *,
    local_available: bool,
    local_model_loaded: bool,
    configured_model_path: str | None,
    external_fallback_enabled: bool,
    external_provider_key: str | None,
    active_session_count: int,
    total_messages: int,
    llama_cpp_installed: bool,
) -> dict[str, Any]:
    return {
        "local_available": local_available,
        "local_model_loaded": local_model_loaded,
        "configured_model_path": mask_model_path(configured_model_path),
        "llama_cpp_installed": llama_cpp_installed,
        "external_fallback_enabled": external_fallback_enabled,
        "external_provider_key": external_provider_key,
        "active_session_count": active_session_count,
        "total_messages": total_messages,
    }
