"""MB-29: Diagnostics Formatter -- pure. Assembles the `/diagnostics`
response shape. Reuses MB-28's own `mask_model_path()` directly (not
re-implemented) so a configured model path is always reported as a
filename only, never a full absolute path.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.llm_runtime.runtime_diagnostics_builder import mask_model_path


def build_diagnostics(
    *,
    hardware: dict[str, Any],
    scanned_model_count: int,
    configured_model_path: str | None,
    local_model_available: bool,
    additional_model_dirs_count: int,
    configured_external_providers: list[str],
) -> dict[str, Any]:
    return {
        "hardware": hardware,
        "scanned_model_count": scanned_model_count,
        "configured_model_path": mask_model_path(configured_model_path),
        "local_model_available": local_model_available,
        "additional_model_dirs_count": additional_model_dirs_count,
        "configured_external_providers": list(configured_external_providers),
    }
