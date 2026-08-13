"""MB-27: Provider Settings Sanitizer -- pure, defensive last-pass.
Every outbound dict (list or detail response) is run through this
function before leaving the service, as a structural guarantee even if
an upstream builder ever regresses. Strips any key matching a
secret-shaped name, recursively.
"""

from __future__ import annotations

from typing import Any

_FORBIDDEN_KEY_SUBSTRINGS = ("encrypted_value", "api_key", "secret_value", "plaintext")
_FORBIDDEN_EXACT_KEYS = frozenset({"value", "encrypted_value"})


def _is_forbidden_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in _FORBIDDEN_EXACT_KEYS:
        return True
    return any(token in lowered for token in _FORBIDDEN_KEY_SUBSTRINGS)


def sanitize(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {
            key: sanitize(value)
            for key, value in payload.items()
            if not _is_forbidden_key(key)
        }
    if isinstance(payload, list):
        return [sanitize(item) for item in payload]
    return payload
