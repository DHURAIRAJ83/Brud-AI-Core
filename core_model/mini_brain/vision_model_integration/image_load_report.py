"""MB-15: Image Load report -- pure. Stage 1 summarizes which of
MB-14's already-extracted images this session will run a vision
provider against. MB-15 never re-extracts an image itself -- it only
reads MB-14's own already-recorded image metadata.
"""

from __future__ import annotations

from typing import Any


def summarize_loaded_images(*, images: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "image_count": len(images),
        "pages": sorted({image["page_number"] for image in images}),
        "total_bytes": sum(image["file_size_bytes"] for image in images),
        "source": "MB-14 Vision Intelligence (read-only)",
    }
