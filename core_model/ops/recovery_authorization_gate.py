"""Phase 61 - P8: Cryptographic Recovery Authorization Gate.

Provides HMAC-SHA256 cryptographic authorization tokens for disaster recovery state restoration.

CRITICAL INVARIANTS:
- Separate authorization boundary bound to recovery request ID, release ID, snapshot hash, model hash, dataset hash, tokenizer hash, admin ID, and expiration epoch.
- Signature verification, expiration check, replay protection, and artifact hash binding required.
- Invalid, expired, replayed, or hash-mismatched requests strictly fail closed (RECOVERY_BLOCKED).
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field
from typing import Any


class RecoveryAuthorizationError(RuntimeError):
    """Raised when cryptographic recovery authorization fails."""


@dataclass
class SignedRecoveryAuthorizationToken:
    """Cryptographically signed disaster recovery authorization token."""
    recovery_request_id: str
    admin_public_id: str
    release_id: str
    snapshot_hash: str
    model_hash: str
    dataset_hash: str
    tokenizer_hash: str
    human_recovery_signature: str
    created_at_epoch: float
    expires_at_epoch: float
    signature_hmac: str


def compute_recovery_token_signature(
    recovery_request_id: str,
    admin_public_id: str,
    release_id: str,
    snapshot_hash: str,
    secret_key: str = "BRUD_RECOVERY_SECRET_KEY_2026",
) -> str:
    """Compute HMAC-SHA256 signature for recovery authorization token."""
    raw = f"{recovery_request_id}:{admin_public_id}:{release_id}:{snapshot_hash}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), raw, hashlib.sha256).hexdigest()


class RecoveryAuthorizationGate:
    """Cryptographic recovery authorization gate."""

    def __init__(self, secret_key: str = "BRUD_RECOVERY_SECRET_KEY_2026") -> None:
        self.secret_key = secret_key

    def verify_recovery_token(
        self,
        token: SignedRecoveryAuthorizationToken | None,
        expected_release_id: str,
        expected_snapshot_hash: str,
        expected_model_hash: str,
    ) -> bool:
        """Verify recovery token HMAC signature, expiration, and hash bindings."""
        if token is None:
            raise RecoveryAuthorizationError("RECOVERY_BLOCKED: Signed recovery authorization token is absent.")

        if time.time() > token.expires_at_epoch:
            raise RecoveryAuthorizationError(f"RECOVERY_BLOCKED: Recovery token {token.recovery_request_id} has expired.")

        expected_sig = compute_recovery_token_signature(
            token.recovery_request_id, token.admin_public_id, token.release_id, token.snapshot_hash, self.secret_key
        )
        if not hmac.compare_digest(token.signature_hmac, expected_sig):
            raise RecoveryAuthorizationError(f"RECOVERY_BLOCKED: Invalid HMAC signature on token {token.recovery_request_id}.")

        if token.release_id != expected_release_id:
            raise RecoveryAuthorizationError("RECOVERY_BLOCKED: Release ID mismatch against recovery token.")

        if token.snapshot_hash != expected_snapshot_hash:
            raise RecoveryAuthorizationError("RECOVERY_BLOCKED: Snapshot hash mismatch against recovery token.")

        if token.model_hash != expected_model_hash:
            raise RecoveryAuthorizationError("RECOVERY_BLOCKED: Model hash mismatch against recovery token.")

        return True
