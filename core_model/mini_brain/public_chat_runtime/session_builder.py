"""MB-23: Session Builder -- pure. Builds the anonymized session shape
MB-23 persists -- a raw client-identifying key (IP, client token) is
hashed with a server-side salt and never stored or returned in the
clear. The hash is deterministic (same key + salt always produces the
same hash) so repeat visits from the same client can be correlated for
analytics without ever recovering the underlying identity.
"""

from __future__ import annotations

import hashlib
from typing import Any

SUPPORTED_LANGUAGES = ("auto", "ta", "en")


def hash_client_key(*, raw_client_key: str, salt: str) -> str:
    if not raw_client_key:
        raise ValueError("raw_client_key must not be empty")
    if not salt:
        raise ValueError("salt must not be empty")
    return hashlib.sha256(f"{salt}:{raw_client_key}".encode("utf-8")).hexdigest()


def build_session(*, raw_client_key: str, salt: str, language: str = "auto") -> dict[str, Any]:
    if language not in SUPPORTED_LANGUAGES:
        language = "auto"
    return {
        "user_session_hash": hash_client_key(raw_client_key=raw_client_key, salt=salt),
        "language": language,
        "status": "active",
        "message_count": 0,
        "satisfaction_score": None,
        "unresolved_count": 0,
        "disclosure": "user_session_hash is a one-way hash of the client key and salt -- the raw client key is never stored",
    }
