"""MB-29: Hardware Probe -- real, read-only OS/hardware introspection.
Uses `psutil` when it's installed; falls back to the standard library
(`/proc/meminfo` on Linux, `GlobalMemoryStatusEx` via `ctypes` on
Windows) otherwise. Never a subprocess, never a network call, never a
write. This is one of the two disclosed real-I/O modules in this
package -- see `__init__.py`.

Honest limitation: on a platform that is neither Linux nor Windows
(e.g. macOS, used only in this dev environment), the stdlib fallback
for RAM figures honestly returns 0.0 rather than guessing -- CPU
count, disk space, architecture, OS name, and Python version are all
still real and correct everywhere via the standard library.
"""

from __future__ import annotations

import platform
import shutil
from pathlib import Path
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]

_RAM_TIERS: tuple[tuple[float, str], ...] = (
    (4.0, "4GB"), (6.0, "6GB"), (8.0, "8GB"), (16.0, "16GB"),
)
_RAM_TIER_MAX = "32GB+"


def _memory_info_linux() -> tuple[float, float]:
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                key, _, rest = line.partition(":")
                parts = rest.strip().split()
                if parts:
                    info[key] = int(parts[0])
        total_gb = info.get("MemTotal", 0) / (1024 * 1024)
        available_gb = info.get("MemAvailable", info.get("MemFree", 0)) / (1024 * 1024)
        return round(total_gb, 2), round(available_gb, 2)
    except (OSError, ValueError, IndexError):
        return 0.0, 0.0


def _memory_info_windows() -> tuple[float, float]:
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
        gib = 1024 ** 3
        return round(stat.ullTotalPhys / gib, 2), round(stat.ullAvailPhys / gib, 2)
    except (AttributeError, OSError, ImportError):
        return 0.0, 0.0


def _memory_info_stdlib() -> tuple[float, float]:
    system = platform.system()
    if system == "Linux":
        return _memory_info_linux()
    if system == "Windows":
        return _memory_info_windows()
    return 0.0, 0.0


def _memory_info() -> tuple[float, float]:
    if psutil is not None:
        virtual = psutil.virtual_memory()
        gib = 1024 ** 3
        return round(virtual.total / gib, 2), round(virtual.available / gib, 2)
    return _memory_info_stdlib()


def _cpu_info() -> tuple[int, int]:
    if psutil is not None:
        physical = psutil.cpu_count(logical=False) or 0
        logical = psutil.cpu_count(logical=True) or 0
        return physical, logical
    logical = __import__("os").cpu_count() or 0
    return logical, logical  # no clean stdlib way to distinguish physical cores


def _disk_free_gb(disk_check_path: Path) -> float:
    try:
        usage = shutil.disk_usage(disk_check_path)
        return round(usage.free / (1024 ** 3), 2)
    except OSError:
        return 0.0


def _ram_tier(total_ram_gb: float) -> str:
    for threshold, label in _RAM_TIERS:
        if total_ram_gb <= threshold:
            return label
    return _RAM_TIER_MAX


def probe(*, disk_check_path: Path | str = ".") -> dict[str, Any]:
    total_ram_gb, available_ram_gb = _memory_info()
    cpu_cores, cpu_threads = _cpu_info()
    return {
        "total_ram_gb": total_ram_gb,
        "available_ram_gb": available_ram_gb,
        "cpu_cores": cpu_cores,
        "cpu_threads": cpu_threads,
        "architecture": platform.machine(),
        "os_name": platform.system(),
        "disk_free_gb": _disk_free_gb(Path(disk_check_path)),
        "python_version": platform.python_version(),
        "recommended_ram_tier": _ram_tier(total_ram_gb),
        "psutil_available": psutil is not None,
    }
