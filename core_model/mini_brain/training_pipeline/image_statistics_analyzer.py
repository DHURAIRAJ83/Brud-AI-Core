"""MB-18: Image Statistics Analyzer -- pure. Reuses MB-14's own
already-extracted image metadata (real checksums, real pixel
dimensions) -- never re-extracts or re-measures an image. Processes
one image record at a time so memory stays bounded regardless of how
many images a dataset contains.
"""

from __future__ import annotations

from typing import Any


def analyze_image_statistics(*, images: list[dict[str, Any]]) -> dict[str, Any]:
    if not images:
        return {
            "image_count": 0, "total_pixels": 0, "average_width": None, "average_height": None,
            "total_bytes": 0, "duplicate_checksum_count": 0,
            "disclosure": "no images were linked to any collected dataset -- this is a text-only training package",
        }

    total_pixels = 0
    total_width = 0
    total_height = 0
    total_bytes = 0
    checksum_counts: dict[str, int] = {}

    for image in images:
        width = image.get("width_pixels", 0)
        height = image.get("height_pixels", 0)
        total_pixels += width * height
        total_width += width
        total_height += height
        total_bytes += image.get("file_size_bytes", 0)
        checksum = image.get("checksum_sha256")
        if checksum:
            checksum_counts[checksum] = checksum_counts.get(checksum, 0) + 1

    count = len(images)
    duplicate_count = sum(c - 1 for c in checksum_counts.values() if c > 1)

    return {
        "image_count": count, "total_pixels": total_pixels,
        "average_width": round(total_width / count, 1), "average_height": round(total_height / count, 1),
        "total_bytes": total_bytes, "duplicate_checksum_count": duplicate_count,
    }
