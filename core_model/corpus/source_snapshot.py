"""Immutable source snapshots.

A snapshot is never updated in place once ``ready`` -- any content
change (a new file, a changed checksum) creates a new snapshot with an
incremented version number, never an in-place edit.
"""

from __future__ import annotations

import hashlib
from typing import Any


def file_inventory_checksum(files: list[dict[str, Any]]) -> str:
    """Deterministic checksum over the sorted (filename, checksum)
    pairs -- order-independent, so re-registering the same files in a
    different order never produces a spurious new snapshot."""

    pairs = sorted(
        f"{item['logical_filename']}:{item['checksum_sha256']}" for item in files
    )
    return hashlib.sha256("|".join(pairs).encode("utf-8")).hexdigest()


def next_snapshot_version(existing_versions: list[int]) -> int:
    return (max(existing_versions) + 1) if existing_versions else 1


def snapshot_requires_new_version(
    *, previous_file_inventory_checksum: str | None, current_file_inventory_checksum: str
) -> bool:
    return previous_file_inventory_checksum != current_file_inventory_checksum


def validate_snapshot_ready(
    *, total_files: int, total_bytes: int, maximum_source_bytes: int
) -> tuple[bool, str | None]:
    if total_files <= 0:
        return False, "snapshot_has_no_files"
    if total_bytes <= 0:
        return False, "snapshot_has_no_content"
    if total_bytes > maximum_source_bytes:
        return False, "snapshot_exceeds_maximum_source_bytes"
    return True, None
