"""MB-14: bounded, read-only image-byte extraction and real pixel
analysis for Vision Intelligence.

No existing service in this codebase extracts actual image bytes from
a PDF -- `document_service.py`'s own PyMuPDF usage only ever counts
embedded images per page (`len(page.get_images(full=True))`) to
decide OCR strategy (confirmed by audit). This is therefore the first
real image-byte extraction in this codebase, built directly on
PyMuPDF and Pillow -- both already dependencies of this project's
existing OCR pipeline, never a new library. It reads an already-
validated, already-stored PDF file via `DocumentService`'s own public
`.get()`/`.artifact()` methods and opens it read-only; it never writes
to the PDF file itself or to any Document Workspace table.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz
from PIL import Image, ImageFilter

MAX_IMAGES_PER_DOCUMENT = 200
MAX_IMAGES_PER_PAGE = 20
_EXIF_ORIENTATION_TAG = 274
_EXIF_ROTATION_BY_ORIENTATION = {3: 180, 6: 90, 8: 270}


def extract_images(*, pdf_path: Path) -> list[dict[str, Any]]:
    """Extracts every embedded image from every page of the given PDF,
    bounded to MAX_IMAGES_PER_DOCUMENT total (MAX_IMAGES_PER_PAGE per
    page). Opens the file read-only and never modifies it."""
    images: list[dict[str, Any]] = []
    document = fitz.open(pdf_path)
    try:
        for page_index in range(len(document)):
            if len(images) >= MAX_IMAGES_PER_DOCUMENT:
                break
            page = document[page_index]
            for image_index, image_info in enumerate(page.get_images(full=True)[:MAX_IMAGES_PER_PAGE]):
                if len(images) >= MAX_IMAGES_PER_DOCUMENT:
                    break
                extracted = document.extract_image(image_info[0])
                image_bytes = extracted["image"]
                images.append({
                    "page_number": page_index + 1,
                    "image_index": image_index,
                    "image_format": extracted["ext"],
                    "width_pixels": extracted["width"],
                    "height_pixels": extracted["height"],
                    "file_size_bytes": len(image_bytes),
                    "checksum_sha256": hashlib.sha256(image_bytes).hexdigest(),
                    "image_bytes": image_bytes,
                })
    finally:
        document.close()
    return images


def analyze_pixels(*, image_bytes: bytes) -> dict[str, Any]:
    """Real pixel statistics via Pillow: brightness/contrast from a
    grayscale histogram, a blur proxy from edge-detection variance,
    and rotation from the image's own real EXIF orientation tag."""
    with Image.open(BytesIO(image_bytes)) as image:
        exif_rotation = 0
        try:
            exif = image.getexif()
            orientation_value = exif.get(_EXIF_ORIENTATION_TAG)
            if orientation_value is not None:
                exif_rotation = _EXIF_ROTATION_BY_ORIENTATION.get(orientation_value, 0)
        except (AttributeError, ValueError, KeyError):
            exif_rotation = 0

        grayscale = image.convert("L")
        width, height = grayscale.size
        histogram = grayscale.histogram()
        total_pixels = sum(histogram) or 1
        brightness_mean = sum(i * count for i, count in enumerate(histogram)) / total_pixels
        variance = sum(((i - brightness_mean) ** 2) * count for i, count in enumerate(histogram)) / total_pixels
        contrast_std = variance**0.5

        edges = grayscale.filter(ImageFilter.FIND_EDGES)
        edge_histogram = edges.histogram()
        edge_total = sum(edge_histogram) or 1
        edge_mean = sum(i * count for i, count in enumerate(edge_histogram)) / edge_total
        blur_variance = sum(((i - edge_mean) ** 2) * count for i, count in enumerate(edge_histogram)) / edge_total

        return {
            "width": width, "height": height, "brightness_mean": round(brightness_mean, 2),
            "contrast_std": round(contrast_std, 2), "blur_variance": round(blur_variance, 2),
            "exif_rotation": exif_rotation,
        }


__all__ = ["extract_images", "analyze_pixels", "MAX_IMAGES_PER_DOCUMENT", "MAX_IMAGES_PER_PAGE"]
