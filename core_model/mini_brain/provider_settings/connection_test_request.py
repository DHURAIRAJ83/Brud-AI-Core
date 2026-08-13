"""MB-27: Connection Test Request -- pure. Builds the normalized
request shape a connection adapter (in `backend/services/
provider_settings_connection_adapters.py`, outside this pure package)
consumes. Never performs any I/O -- this is "what should be asked,"
not "what actually gets asked over the network."
"""

from __future__ import annotations

from typing import Any

DEFAULT_TEST_TIMEOUT_SECONDS = 10.0
MAX_TEST_TIMEOUT_SECONDS = 30.0
MIN_TEST_TIMEOUT_SECONDS = 1.0


def clamp_timeout(timeout_seconds: float | None) -> float:
    if timeout_seconds is None:
        return DEFAULT_TEST_TIMEOUT_SECONDS
    return min(max(timeout_seconds, MIN_TEST_TIMEOUT_SECONDS), MAX_TEST_TIMEOUT_SECONDS)


def build(*, provider_key: str, decrypted_api_key: str | None, timeout_seconds: float | None) -> dict[str, Any]:
    return {
        "provider_key": provider_key,
        "decrypted_api_key": decrypted_api_key,
        "timeout_seconds": clamp_timeout(timeout_seconds),
    }
