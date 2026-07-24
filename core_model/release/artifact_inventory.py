"""Bounded, deterministic artifact-inventory validation.

Never accepts an arbitrary filesystem path. Every artifact must resolve
to a location confined inside one of a small set of approved roots
(``BRUD_RELEASE_ALLOWED_ARTIFACT_ROOTS``, resolved by the service layer)
— this module only checks confinement given the resolved paths, it never
constructs paths from unvalidated user input itself.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any

_UNEXPECTED_EXECUTABLE_SUFFIXES = (".exe", ".sh", ".bat", ".cmd", ".ps1", ".msi", ".dll", ".so")


def file_checksum(path: Path, *, algorithm: str = "sha256") -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_confined_path(root: Path, relative_key: str) -> Path:
    """Resolve ``relative_key`` under ``root``, rejecting escape attempts.

    Rejects absolute paths, ``..`` traversal, and symlinks that resolve
    outside ``root`` — the same confinement contract as
    ``TrainingCheckpointManager.verify()``.
    """

    if Path(relative_key).is_absolute():
        raise ValueError("artifact storage key must be relative, not absolute")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_key).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError("artifact storage key escapes the approved artifact root")
    return candidate


def verify_artifact_size(size_bytes: int, max_bytes: int) -> bool:
    return 0 <= size_bytes <= max_bytes


def detect_unexpected_executable(path: Path) -> bool:
    if path.suffix.lower() in _UNEXPECTED_EXECUTABLE_SUFFIXES:
        return True
    return path.is_file() and os.access(path, os.X_OK)


def classify_artifact_verification(
    *,
    exists: bool,
    path_confined: bool,
    size_ok: bool,
    checksum_matches: bool | None,
    structurally_valid: bool = True,
) -> str:
    """Returns one of VERIFICATION_STATUSES."""

    if not path_confined:
        return "invalid"
    if not exists:
        return "missing"
    if not size_ok or not structurally_valid:
        return "invalid"
    if checksum_matches is False:
        return "checksum_mismatch"
    if checksum_matches is None:
        return "pending"
    return "verified"


def required_artifact_types(
    *, instruction_tuned: bool, evaluation_available: bool
) -> tuple[str, ...]:
    """The minimum artifact-type set a candidate must collect, given lineage."""

    required = [
        "model_checkpoint", "model_config", "tokenizer_model", "tokenizer_vocab",
        "tokenizer_manifest", "base_training_manifest",
    ]
    if instruction_tuned:
        required.append("instruction_tuning_manifest")
    if evaluation_available:
        required.append("evaluation_manifest")
    return tuple(required)


def missing_required_artifact_types(
    collected: dict[str, Any], required: tuple[str, ...]
) -> list[str]:
    return [
        artifact_type
        for artifact_type in required
        if collected.get(artifact_type, {}).get("verification_status") != "verified"
    ]
