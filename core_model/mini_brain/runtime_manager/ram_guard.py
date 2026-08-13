"""MB-30: RAM Guard -- pure. Per the phase spec's own section 6:
before a load, keep at least 1.5GB free; refuse the load if unsafe;
return a bilingual warning.
"""

from __future__ import annotations

from typing import Any

MIN_FREE_RAM_GB = 1.5


def check_load_safety(*, available_ram_gb: float, estimated_model_ram_gb: float) -> dict[str, Any]:
    projected_free_ram_gb = round(available_ram_gb - estimated_model_ram_gb, 2)
    safe = projected_free_ram_gb >= MIN_FREE_RAM_GB
    warning_en = None
    warning_ta = None
    if not safe:
        warning_en = (
            f"Loading this model would leave only {projected_free_ram_gb}GB RAM free "
            f"(minimum {MIN_FREE_RAM_GB}GB required) -- refusing to load."
        )
        warning_ta = (
            f"இந்த மாடலை ஏற்றினால் {projected_free_ram_gb}GB RAM மட்டுமே மீதமிருக்கும் "
            f"(குறைந்தபட்சம் {MIN_FREE_RAM_GB}GB தேவை) -- ஏற்ற மறுக்கப்படுகிறது."
        )
    return {
        "safe": safe,
        "available_ram_gb": available_ram_gb,
        "estimated_model_ram_gb": estimated_model_ram_gb,
        "projected_free_ram_gb": projected_free_ram_gb,
        "minimum_free_ram_gb": MIN_FREE_RAM_GB,
        "warning_en": warning_en,
        "warning_ta": warning_ta,
    }
