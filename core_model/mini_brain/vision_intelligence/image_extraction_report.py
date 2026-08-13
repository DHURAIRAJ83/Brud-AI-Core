"""MB-14: Image Extraction Report -- pure. Summarizes already-extracted
image metadata (page/index/format/size/checksum, extracted by the
service layer's own bounded PyMuPDF read of the already-stored PDF
file -- never here). Duplicate detection is exact byte-checksum only;
this codebase has no perceptual/near-duplicate image hashing anywhere.
Never modifies the original document.
"""

from __future__ import annotations

from typing import Any


def summarize_extraction(*, images: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(images)
    images_per_page: dict[str, int] = {}
    format_counts: dict[str, int] = {}
    checksums: dict[str, list[str]] = {}
    total_bytes = 0

    for image in images:
        page_key = str(image["page_number"])
        images_per_page[page_key] = images_per_page.get(page_key, 0) + 1
        format_counts[image["image_format"]] = format_counts.get(image["image_format"], 0) + 1
        total_bytes += image["file_size_bytes"]
        checksums.setdefault(image["checksum_sha256"], []).append(image["public_id"])

    exact_duplicate_groups = [ids for ids in checksums.values() if len(ids) > 1]

    return {
        "total_images": total,
        "images_per_page": images_per_page,
        "format_counts": format_counts,
        "total_bytes": total_bytes,
        "exact_duplicate_groups": exact_duplicate_groups,
        "exact_duplicate_count": sum(len(group) for group in exact_duplicate_groups),
        "never_modified_original": True,
        "disclosure": (
            "duplicate detection here is exact byte-checksum only -- no perceptual/near-duplicate "
            "image hashing exists anywhere in this codebase"
        ),
    }
