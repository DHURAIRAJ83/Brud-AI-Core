"""Phase 20 Step 27 -- bounded, in-process Trusted Web search cache.

Same style as `public_chat_rate_limiter.py`: a bounded, thread-safe,
CPU-first in-memory dict -- no external cache/queue. One process, one
cache -- a documented, known limitation for multi-process deployment,
matching the rate limiter's own precedent exactly.

Cache key is `(normalized_query, language, freshness_class,
policy_version, provider_name)` (Step 27's own required key shape).
Freshness-sensitive queries (`real_time`) get a short TTL via the
caller passing a smaller `ttl_seconds`; nothing here ever serves a
result past its own recorded expiry. The cached value is a `WebAnswer`
(this module never inspects it) -- never contains secrets or
per-user private context, since Trusted Web evidence is already
public, policy-approved source content, not user-specific.
"""

from __future__ import annotations

import threading
import time
from typing import Any

MAX_CACHE_ENTRIES = 256

_lock = threading.Lock()
_entries: dict[tuple, tuple[float, Any]] = {}


def cache_key(
    *, normalized_query: str, language: str, freshness_class: str, policy_version: str,
    provider_name: str,
) -> tuple:
    return (normalized_query, language, freshness_class, policy_version, provider_name)


def get_cached(key: tuple) -> Any | None:
    with _lock:
        entry = _entries.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        if time.monotonic() >= expires_at:
            _entries.pop(key, None)
            return None
        return value


def set_cached(key: tuple, value: Any, *, ttl_seconds: float) -> None:
    if ttl_seconds <= 0:
        return
    with _lock:
        if len(_entries) >= MAX_CACHE_ENTRIES and key not in _entries:
            oldest_key = min(_entries, key=lambda k: _entries[k][0])
            _entries.pop(oldest_key, None)
        _entries[key] = (time.monotonic() + ttl_seconds, value)


def reset_cache() -> None:
    """Test-only: clear all cached entries."""

    with _lock:
        _entries.clear()


__all__ = ["cache_key", "get_cached", "reset_cache", "set_cached"]
