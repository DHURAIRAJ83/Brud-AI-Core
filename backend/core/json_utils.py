"""Safe, deterministic handling for JSON stored in SQLite."""

import json
from typing import Any

from backend.core.config import get_settings


class JsonValidationError(ValueError):
    """Raised when metadata cannot be represented safely as bounded JSON."""


def _validate(value: Any, depth: int = 0) -> None:
    if depth > 8:
        raise JsonValidationError("JSON metadata exceeds maximum depth")
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for item in value:
            _validate(item, depth + 1)
        return
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise JsonValidationError("JSON object keys must be strings")
        for item in value.values():
            _validate(item, depth + 1)
        return
    raise JsonValidationError(f"unsupported JSON value type: {type(value).__name__}")


def dumps_json(value: Any, max_bytes: int | None = None) -> str:
    """Serialize JSON deterministically and enforce the configured byte bound."""

    _validate(value)
    serialized = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    limit = max_bytes if max_bytes is not None else get_settings().max_metadata_bytes
    if len(serialized.encode("utf-8")) > limit:
        raise JsonValidationError(f"JSON metadata exceeds {limit} bytes")
    return serialized


def loads_json(value: str | None, *, default: Any = None) -> Any:
    """Decode ordinary JSON only; arbitrary object deserialization is impossible."""

    if not value:
        return {} if default is None else default
    decoded = json.loads(value)
    _validate(decoded)
    return decoded


SECRET_KEYS = {"secret", "password", "token", "api_key", "apikey", "authorization"}


def redact_secrets(value: Any) -> Any:
    """Recursively redact values whose keys look secret-bearing."""

    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if any(marker in key.lower() for marker in SECRET_KEYS)
            else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    return value
