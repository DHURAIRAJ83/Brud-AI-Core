"""Checkpoint manifest helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from backend.core.json_utils import dumps_json


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(directory: Path, files: list[str], metadata: dict[str, Any]) -> str:
    manifest = {"files": files, "metadata": metadata}
    path = directory / "artifact_manifest.json"
    path.write_text(dumps_json(manifest) + "\n", encoding="utf-8")
    return sha256_file(path)
