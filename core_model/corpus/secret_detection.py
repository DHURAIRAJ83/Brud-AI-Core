"""Credential and secret detection.

Reuses Phase 17's ``core_model.conversation.memory_safety`` pattern set
unchanged for passwords, API keys, access tokens, private keys,
payment-card data, bank credentials, authentication cookies, absolute
paths, and environment-variable dumps -- never a second secret-pattern
implementation. Adds session-ID and database-connection-string
patterns this corpus phase specifically needs. Every one of these
categories is always blocked, regardless of corpus policy -- there is
no "redact and keep" option for a genuine credential.
"""

from __future__ import annotations

import re
from typing import Any

from core_model.conversation.memory_safety import detect_safety_signals

_SESSION_ID_PATTERN = re.compile(
    r"\b(session[_-]?id|sid)\s*[:=]\s*[A-Za-z0-9_-]{16,}\b", re.IGNORECASE
)
_DB_CONNECTION_STRING_PATTERN = re.compile(
    r"\b(postgres|mysql|mongodb|redis)://\S+:\S+@\S+", re.IGNORECASE
)

# Every category here always blocks -- never redact-and-keep.
ALWAYS_BLOCKED_CATEGORIES = frozenset(
    {
        "password", "api_key", "access_token", "private_key", "payment_card", "bank_account",
        "authentication_cookie", "session_id", "database_credentials",
    }
)


def detect_secrets(text: str) -> dict[str, Any]:
    base = detect_safety_signals(text)
    matched = list(base["matched_categories"])
    if _SESSION_ID_PATTERN.search(text):
        matched.append("session_id")
    if _DB_CONNECTION_STRING_PATTERN.search(text):
        matched.append("database_credentials")

    blocking_matches = [category for category in matched if category in ALWAYS_BLOCKED_CATEGORIES]
    status = "blocked" if blocking_matches else ("requires_review" if matched else "safe")
    return {"status": status, "matched_categories": sorted(set(matched))}
