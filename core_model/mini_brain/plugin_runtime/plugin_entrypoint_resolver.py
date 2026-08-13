"""MB-25: Plugin Entrypoint Resolver -- resolves a plugin's declared
entrypoint file within its own package directory using the same
confined-path helper MB-18 through MB-24 already share
(`core_model.release.artifact_inventory.resolve_confined_path()`) --
never a second path-confinement implementation. Like that helper
itself, this performs real path canonicalization (`Path.resolve()`)
but never reads file content and never executes anything.
"""

from __future__ import annotations

from pathlib import Path

from core_model.release.artifact_inventory import resolve_confined_path


def resolve_entrypoint(*, package_dir: Path, entrypoint: str) -> Path:
    if not entrypoint.endswith(".py"):
        raise ValueError("entrypoint must be a .py file")
    resolved = resolve_confined_path(package_dir, entrypoint)
    if not resolved.exists():
        raise FileNotFoundError(f"entrypoint file does not exist: {entrypoint}")
    return resolved
