"""Training metrics helpers."""

from __future__ import annotations

import math
import os


def finite(value: float | None) -> bool:
    return value is None or math.isfinite(value)


def process_memory_bytes() -> int | None:
    try:
        pages = int(open("/proc/self/statm", encoding="utf-8").read().split()[1])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return None


def available_memory_bytes() -> int | None:
    try:
        for line in open("/proc/meminfo", encoding="utf-8"):
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except OSError:
        return None
    return None
