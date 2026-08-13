"""MB-30: Disk Space Guard -- pure. Given already-measured available
and required byte counts (the service layer calls `shutil.disk_usage()`
itself), decides whether a download is safe -- never touches the
filesystem here.
"""

from __future__ import annotations

from typing import Any

_SAFETY_MARGIN_BYTES = 500 * 1024 * 1024  # 500MB headroom beyond the exact file size


def check(*, available_bytes: int, required_bytes: int) -> dict[str, Any]:
    required_with_margin = required_bytes + _SAFETY_MARGIN_BYTES
    safe = available_bytes >= required_with_margin
    return {
        "safe": safe,
        "available_bytes": available_bytes,
        "required_bytes": required_bytes,
        "safety_margin_bytes": _SAFETY_MARGIN_BYTES,
        "shortfall_bytes": max(0, required_with_margin - available_bytes),
        "message_en": "Sufficient disk space." if safe else "Insufficient disk space to download this model -- refusing to start.",
        "message_ta": "போதுமான வட்டு இடம் உள்ளது." if safe else "இந்த மாடலைப் பதிவிறக்க போதுமான வட்டு இடம் இல்லை -- தொடங்க மறுக்கப்படுகிறது.",
    }
