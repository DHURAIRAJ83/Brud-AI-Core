"""Minimal in-process fixed-window rate limiter for public chat (Step
22/34). No external cache/queue -- a bounded, thread-safe, CPU-first
in-memory counter, matching this codebase's own established pattern
for in-process locking (e.g. `production_regression_service.py`'s
`_RUN_LOCKS`). One process, one counter table -- documented, known
limitation: a multi-process/multi-worker deployment would need a
shared store (Redis or similar) instead; out of scope for this phase.
"""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_window_start_by_key: dict[str, float] = {}
_count_by_key: dict[str, int] = {}


def check_rate_limit(key: str, *, max_requests: int, window_seconds: int) -> bool:
    """Returns True if the request is allowed, False if rate-limited.
    Fixed-window: the counter resets whenever more than `window_seconds`
    has elapsed since the window for `key` started."""

    now = time.monotonic()
    with _lock:
        window_start = _window_start_by_key.get(key)
        if window_start is None or (now - window_start) >= window_seconds:
            _window_start_by_key[key] = now
            _count_by_key[key] = 1
            return True
        if _count_by_key[key] >= max_requests:
            return False
        _count_by_key[key] += 1
        return True


def reset_rate_limits() -> None:
    """Test-only: clear all counters."""

    with _lock:
        _window_start_by_key.clear()
        _count_by_key.clear()


__all__ = ["check_rate_limit", "reset_rate_limits"]
