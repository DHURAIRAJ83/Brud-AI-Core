"""MB-24: Plugin Execution Token Builder -- pure. Builds the task
spec's own Step 11 token payload (plugin_id, granted_scopes, issued_at,
expires_at, user_id_hash, session_id_hash, nonce) and its SHA-256 hash,
reusing `core_model.release.manifest.manifest_checksum()` directly --
the same canonical-JSON-then-SHA-256 function MB-18 through MB-23
already share -- rather than a second hashing implementation.

The `nonce` is never generated inside this module: a pure function
cannot honestly produce randomness and still be deterministic, so the
service layer (impure, permitted a real random source) generates it
and passes it in here. Only `token_hash` should ever be persisted --
the raw payload/token string must never be stored, only returned once
to the caller that requested it.
"""

from __future__ import annotations

from typing import Any

from core_model.release.manifest import manifest_checksum

MAX_GRANTED_SCOPES = 20
DEFAULT_TOKEN_TTL_SECONDS = 300.0


def build_execution_token(
    *, plugin_public_id: str, granted_scopes: list[str], user_id_hash: str, session_id_hash: str,
    issued_at_epoch_seconds: float, nonce: str, ttl_seconds: float = DEFAULT_TOKEN_TTL_SECONDS,
) -> dict[str, Any]:
    if len(granted_scopes) > MAX_GRANTED_SCOPES:
        raise ValueError(f"granted_scopes exceeds maximum of {MAX_GRANTED_SCOPES}")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    expires_at = issued_at_epoch_seconds + ttl_seconds
    payload = {
        "plugin_id": plugin_public_id, "granted_scopes": sorted(granted_scopes),
        "issued_at": issued_at_epoch_seconds, "expires_at": expires_at, "user_id_hash": user_id_hash,
        "session_id_hash": session_id_hash, "nonce": nonce,
    }
    token_hash = manifest_checksum(payload)

    return {
        "payload": payload, "token_hash": token_hash, "expires_at": expires_at,
        "disclosure": (
            "only token_hash should ever be persisted -- the raw payload must never be stored, only "
            "returned once to the caller; this is governance metadata, never a real cryptographically "
            "signed credential"
        ),
    }


def is_token_expired(*, expires_at_epoch_seconds: float, now_epoch_seconds: float) -> bool:
    return now_epoch_seconds >= expires_at_epoch_seconds
