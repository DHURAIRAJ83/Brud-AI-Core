"""MB-24: Consent Policy Engine -- pure. Decides whether an already-
fetched consent record still satisfies a scope's requirement (honoring
an optional expiry), and builds the shape of a new consent record.
Consent never auto-expires unless a `ttl_seconds` is explicitly
configured by an admin.
"""

from __future__ import annotations

from typing import Any


def is_consent_valid(
    *, consent_given: bool, expires_at_epoch_seconds: float | None, now_epoch_seconds: float,
) -> dict[str, Any]:
    if not consent_given:
        return {"valid": False, "reason": "consent was not given"}
    if expires_at_epoch_seconds is not None and now_epoch_seconds >= expires_at_epoch_seconds:
        return {"valid": False, "reason": "consent has expired"}
    return {"valid": True, "reason": None}


def build_consent_record(
    *, scope_key: str, consent_given: bool, ttl_seconds: float | None, now_epoch_seconds: float,
) -> dict[str, Any]:
    expires_at = now_epoch_seconds + ttl_seconds if (consent_given and ttl_seconds is not None) else None
    return {
        "scope_key": scope_key, "consent_given": consent_given,
        "consent_at": now_epoch_seconds if consent_given else None, "expires_at": expires_at,
        "disclosure": "consent never auto-expires unless ttl_seconds is explicitly configured by an admin",
    }
