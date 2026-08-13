"""MB-30: Install Plan Builder -- pure. `Path` joining is pure data
manipulation (no filesystem touched) -- the actual download/write
happens entirely in the service layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_plan(*, model_id: str, catalog_entry: dict[str, Any], allowed_model_dir: str) -> dict[str, Any]:
    target_path = str(Path(allowed_model_dir) / catalog_entry["file_name"])
    return {
        "model_id": model_id,
        "display_name": catalog_entry["display_name"],
        "family": catalog_entry["family"],
        "quantization": catalog_entry["quantization"],
        "download_url": catalog_entry["download_url"],
        "file_name": catalog_entry["file_name"],
        "target_path": target_path,
        "expected_size_bytes": catalog_entry["expected_size_bytes"],
        "expected_sha256": catalog_entry["sha256"],
    }
