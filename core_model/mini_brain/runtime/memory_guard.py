"""Memory protection -- a fail-closed guard checked before every model
load, mirroring (as an independent implementation, not a shared import)
the same honest measure-or-report-unmeasurable pattern
`InferenceRuntimeService._read_available_memory_bytes` already uses in
the main runtime. On a machine where availability can't be measured,
this refuses to load rather than silently assuming there's enough
room -- fail-closed, not fail-open.
"""

from __future__ import annotations

from pathlib import Path


def read_available_memory_bytes() -> tuple[int, str]:
    """Returns (bytes, label). label is "measured" or "unmeasurable" --
    never a fabricated number when /proc/meminfo can't be read."""

    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        try:
            for line in meminfo.read_text(encoding="utf-8").splitlines():
                if line.startswith("MemAvailable:"):
                    kib = int(line.split()[1])
                    return kib * 1024, "measured"
        except OSError:
            pass
    return 0, "unmeasurable"


def check_memory_guard(*, minimum_available_bytes: int) -> dict[str, object]:
    available_bytes, label = read_available_memory_bytes()
    if label == "unmeasurable":
        return {
            "allowed": False, "available_bytes": 0, "label": label,
            "reason": "memory availability could not be measured -- refusing to load (fail-closed)",
        }
    if available_bytes < minimum_available_bytes:
        return {
            "allowed": False, "available_bytes": available_bytes, "label": label,
            "reason": (
                f"only {available_bytes // (1024*1024)}MB available, "
                f"minimum required is {minimum_available_bytes // (1024*1024)}MB"
            ),
        }
    return {"allowed": True, "available_bytes": available_bytes, "label": label, "reason": None}
