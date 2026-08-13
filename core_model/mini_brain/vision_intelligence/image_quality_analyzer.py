"""MB-14: Image Quality Analyzer -- pure. Scores already-computed real
pixel statistics (resolution from the extracted image's own
dimensions, brightness/contrast from a real grayscale histogram, a
blur proxy from a real edge-variance measurement, rotation from the
image's own real EXIF orientation tag -- all computed once, at the
service layer, via Pillow, already a dependency of this codebase).
Crop and noise detection are honestly NOT implemented -- no capability
for either exists anywhere in this codebase, and neither is fabricated.
"""

from __future__ import annotations

from typing import Any

MIN_RESOLUTION_PIXELS = 100 * 100
LOW_BRIGHTNESS_THRESHOLD = 40.0
HIGH_BRIGHTNESS_THRESHOLD = 215.0
LOW_CONTRAST_THRESHOLD = 15.0
BLUR_VARIANCE_THRESHOLD = 100.0
ISSUE_PENALTY = 15.0
NOT_DETECTED = ("crop", "noise")


def analyze_image_quality(
    *, width: int, height: int, brightness_mean: float, contrast_std: float, blur_variance: float,
    exif_rotation: int | None,
) -> dict[str, Any]:
    issues: list[str] = []
    resolution_pixels = width * height

    if resolution_pixels < MIN_RESOLUTION_PIXELS:
        issues.append("low_resolution")
    if brightness_mean < LOW_BRIGHTNESS_THRESHOLD:
        issues.append("too_dark")
    elif brightness_mean > HIGH_BRIGHTNESS_THRESHOLD:
        issues.append("too_bright")
    if contrast_std < LOW_CONTRAST_THRESHOLD:
        issues.append("low_contrast")
    if blur_variance < BLUR_VARIANCE_THRESHOLD:
        issues.append("possibly_blurry")
    if exif_rotation not in (0, None):
        issues.append(f"rotated_{exif_rotation}_degrees")

    quality_score = round(max(0.0, 100.0 - len(issues) * ISSUE_PENALTY), 1)

    return {
        "width": width, "height": height, "resolution_pixels": resolution_pixels,
        "brightness_mean": brightness_mean, "contrast_std": contrast_std, "blur_variance": blur_variance,
        "exif_rotation": exif_rotation, "issues": issues, "quality_score": quality_score,
        "not_detected": list(NOT_DETECTED),
        "disclosure": (
            "resolution/brightness/contrast/blur/rotation are computed from real pixel data "
            "(Pillow); crop and noise detection are NOT implemented -- no capability for either "
            "exists in this codebase, and neither is fabricated"
        ),
    }
