"""MB-30: Download Progress Tracker -- pure. Given already-observed
byte counts and elapsed time (the service layer streams the real
download), computes percentage/speed/ETA -- never performs the
download itself.
"""

from __future__ import annotations

from typing import Any


def compute_progress(*, bytes_downloaded: int, total_bytes: int, elapsed_seconds: float) -> dict[str, Any]:
    percent = round((bytes_downloaded / total_bytes) * 100, 1) if total_bytes > 0 else 0.0
    speed_bytes_per_sec = bytes_downloaded / elapsed_seconds if elapsed_seconds > 0 else 0.0
    remaining_bytes = max(0, total_bytes - bytes_downloaded)
    eta_seconds = remaining_bytes / speed_bytes_per_sec if speed_bytes_per_sec > 0 else None
    return {
        "percent": min(100.0, percent),
        "bytes_downloaded": bytes_downloaded,
        "total_bytes": total_bytes,
        "speed_mb_per_sec": round(speed_bytes_per_sec / (1024 * 1024), 2),
        "eta_seconds": round(eta_seconds, 1) if eta_seconds is not None else None,
        "complete": bytes_downloaded >= total_bytes > 0,
    }
