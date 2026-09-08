"""Phase 61 - P9: Secret & Key Lifecycle Manager.

Governs versioning, rotation, and revocation of HMAC secrets across system governance boundaries.

CRITICAL INVARIANTS:
- States: ACTIVE | PENDING_ROTATION | RETIRED | REVOKED | UNKNOWN.
- Secret rotation MUST NOT invalidate historical audit chain verification.
- Never exposes raw secrets in logs, contracts, manifests, or exceptions. Only exposes fingerprints and key IDs.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


class SecretLifecycleError(ValueError):
    """Raised when secret rotation or validation fails."""


@dataclass
class SecretMetadataRecord:
    """Safe metadata for a managed cryptographic key/secret."""
    key_id: str
    key_purpose: str  # TRAINING_GATE | PROMOTION_GATE | CANARY_GATE | SNAPSHOT_HMAC | RECOVERY_GATE
    version: int
    fingerprint: str  # SHA-256 fingerprint of raw secret (never store raw secret)
    status: str       # ACTIVE | PENDING_ROTATION | RETIRED | REVOKED | UNKNOWN
    created_at_epoch: float
    activated_at_epoch: float
    retired_at_epoch: float | None = None
    revoked_at_epoch: float | None = None


class SecretLifecycleManager:
    """Manager for cryptographic key versioning, rotation, and revocation."""

    def __init__(self) -> None:
        self._keys: dict[str, SecretMetadataRecord] = {}
        self._raw_secrets: dict[str, str] = {}  # Internal in-memory lookup bound to key_id

    def register_key(
        self,
        key_purpose: str,
        raw_secret: str,
        version: int = 1,
    ) -> SecretMetadataRecord:
        """Register a new secret key version."""
        if not raw_secret or len(raw_secret) < 16:
            raise SecretLifecycleError("Fail-Closed: Secret key must be at least 16 characters.")

        fp = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()[:16]
        key_id = f"key-{key_purpose.lower()}-v{version}"
        now = time.time()

        rec = SecretMetadataRecord(
            key_id=key_id,
            key_purpose=key_purpose,
            version=version,
            fingerprint=fp,
            status="ACTIVE",
            created_at_epoch=now,
            activated_at_epoch=now
        )
        self._keys[key_id] = rec
        self._raw_secrets[key_id] = raw_secret
        return rec

    def rotate_key(self, key_purpose: str, new_raw_secret: str) -> SecretMetadataRecord:
        """Rotate key version for a given purpose while preserving historical key metadata."""
        existing = [k for k in self._keys.values() if k.key_purpose == key_purpose]
        new_version = len(existing) + 1

        # Retire old active key
        for old in existing:
            if old.status == "ACTIVE":
                old.status = "RETIRED"
                old.retired_at_epoch = time.time()

        return self.register_key(key_purpose, new_raw_secret, version=new_version)

    def revoke_key(self, key_id: str) -> SecretMetadataRecord:
        """Revoke a compromised secret key."""
        if key_id not in self._keys:
            raise SecretLifecycleError(f"Key {key_id} not found.")

        rec = self._keys[key_id]
        rec.status = "REVOKED"
        rec.revoked_at_epoch = time.time()
        return rec

    def get_active_secret(self, key_purpose: str) -> tuple[str, str]:
        """Return (key_id, raw_secret) for active key of specified purpose."""
        active = [k for k in self._keys.values() if k.key_purpose == key_purpose and k.status == "ACTIVE"]
        if not active:
            raise SecretLifecycleError(f"Fail-Closed: No active key found for purpose {key_purpose}.")
        key_id = active[0].key_id
        return key_id, self._raw_secrets[key_id]

    def get_historical_secret(self, key_id: str) -> str:
        """Retrieve historical secret for validating historical audit events."""
        if key_id not in self._keys:
            raise SecretLifecycleError(f"Key {key_id} not found.")
        if self._keys[key_id].status == "REVOKED":
            raise SecretLifecycleError(f"Fail-Closed: Key {key_id} has been REVOKED and cannot be used.")
        return self._raw_secrets[key_id]
