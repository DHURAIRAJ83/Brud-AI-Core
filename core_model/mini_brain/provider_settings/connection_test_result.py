"""MB-27: Connection Test Result -- pure. Normalizes whatever raw dict
a connection adapter returns into the canonical, sanitized shape the
service returns to the API -- strips any accidental extra keys
(including any that might carry secret material), guarantees `status`
is one of a fixed vocabulary, and never includes a `text`/body field
(unlike MB-21's `dispatch()`, a connectivity test has no reason to
return generated content).
"""

from __future__ import annotations

from typing import Any

KNOWN_STATUSES = frozenset({"success", "unavailable", "timeout", "failed", "rate_limited", "missing_key"})

# Keys that must never survive into a connection-test result, even if an
# adapter's raw return dict accidentally included one.
_FORBIDDEN_KEYS = frozenset({"api_key", "decrypted_api_key", "encrypted_value", "value", "secret_value"})


def normalize(*, provider_key: str, raw_result: dict[str, Any]) -> dict[str, Any]:
    status = raw_result.get("status")
    if status not in KNOWN_STATUSES:
        status = "failed"
    return {
        "provider_key": provider_key,
        "status": status,
        "latency_ms": float(raw_result.get("latency_ms") or 0.0),
        "error_message": raw_result.get("error_message"),
    }


def contains_forbidden_keys(result: dict[str, Any]) -> bool:
    return bool(_FORBIDDEN_KEYS & set(result.keys()))
