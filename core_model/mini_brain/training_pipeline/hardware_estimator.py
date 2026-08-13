"""MB-18: Hardware Estimator -- pure. Every figure here is explicitly
marked heuristic: no tokenizer was loaded (token count is a character-
count-divided-by-4 approximation, a commonly cited rough ratio, never
a real tokenization), no throughput benchmark was ever executed, and
no training has ever run in this codebase to calibrate these numbers
against reality.
"""

from __future__ import annotations

from typing import Any

CHARS_PER_TOKEN_ESTIMATE = 4
BYTES_PER_TOKEN_ESTIMATE = 4
SMALL_RAM_TOKEN_THRESHOLD = 500_000
LARGE_RAM_TOKEN_THRESHOLD = 5_000_000


def estimate_hardware(
    *, total_character_count: int, image_count: int, total_image_pixels: int, total_image_bytes: int,
    total_text_bytes: int,
) -> dict[str, Any]:
    estimated_tokens = round(total_character_count / CHARS_PER_TOKEN_ESTIMATE)
    estimated_disk_bytes = total_text_bytes + total_image_bytes + estimated_tokens * BYTES_PER_TOKEN_ESTIMATE

    if estimated_tokens < SMALL_RAM_TOKEN_THRESHOLD:
        ram_tier, vram_tier, duration_category = "8GB+", "cpu_only_or_4GB+", "minutes"
        cpu_only_feasible = True
    elif estimated_tokens < LARGE_RAM_TOKEN_THRESHOLD:
        ram_tier, vram_tier, duration_category = "16GB+", "8GB+", "hours"
        cpu_only_feasible = image_count == 0
    else:
        ram_tier, vram_tier, duration_category = "32GB+", "24GB+", "many_hours_to_days"
        cpu_only_feasible = False

    return {
        "estimated_token_count": estimated_tokens, "image_count": image_count,
        "estimated_image_pixels": total_image_pixels, "estimated_disk_bytes": estimated_disk_bytes,
        "ram_tier": ram_tier, "vram_tier": vram_tier, "cpu_only_feasible": cpu_only_feasible,
        "expected_training_duration_category": duration_category,
        "all_estimates_heuristic": True,
        "disclosure": (
            "no tokenizer was loaded (tokens estimated as characters / 4, a rough commonly-cited "
            "ratio), no throughput benchmark was executed, and no training has ever run in this "
            "codebase to calibrate these figures -- every value here is a heuristic, not a measurement"
        ),
    }
