"""Phase 61 - P1: Signed Training Authorization Gate & CLI Bypass Protection.

Enforces cryptographic signed training authorization across all pretraining entry points.
Prevents unauthenticated shell/CLI execution from starting model training, executing
optimizer steps, or mutating model weights.

CRITICAL INVARIANTS:
- DEFAULT: training_execution_authorized = FALSE.
- If signed authorization token is absent, invalid, or expired: ABORT IMMEDIATELY.
- NO optimizer steps executed. NO model weights mutated.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any


class TrainingAuthorizationError(RuntimeError):
    """Raised when training execution is attempted without signed authorization."""


@dataclass(frozen=True)
class SignedTrainingAuthorizationToken:
    """Cryptographic signed token for training authorization."""
    token_id: str
    admin_public_id: str
    dataset_manifest_hash: str
    rights_gate_status: str  # PASS | FAIL
    novelty_gate_status: str  # PASS | FAIL
    provenance_gate_status: str  # PASS | FAIL
    holdout_gate_status: str  # PASS | FAIL
    token_accounting_status: str  # PASS | FAIL
    human_approval_signature: str
    created_at_epoch: float
    expires_at_epoch: float
    signature_hmac: str


def compute_token_signature(
    token_id: str,
    admin_public_id: str,
    dataset_manifest_hash: str,
    secret_key: str = "BRUD_GOVERNANCE_SECRET_KEY_2026",
) -> str:
    """Compute HMAC-SHA256 signature for authorization payload."""
    payload = f"{token_id}:{admin_public_id}:{dataset_manifest_hash}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


class SignedTrainingGateEngine:
    """Gate engine that validates signed authorization tokens prior to pretraining execution."""

    def __init__(
        self,
        runtime_authorized_flag: bool = False,
        secret_key: str = "BRUD_GOVERNANCE_SECRET_KEY_2026",
    ) -> None:
        self.runtime_authorized_flag = runtime_authorized_flag
        self.secret_key = secret_key

    def verify_authorization(
        self,
        token: SignedTrainingAuthorizationToken | None,
        expected_manifest_hash: str | None = None,
        ignore_runtime_flag: bool = False,
    ) -> bool:
        """Verify signed training authorization token. Returns True or raises TrainingAuthorizationError."""

        # 1. Check runtime execution flag
        if not ignore_runtime_flag and not self.runtime_authorized_flag:
            raise TrainingAuthorizationError(
                "TRAINING_EXECUTION_BLOCKED: `training_execution_authorized` is FALSE. "
                "No training execution, optimizer stepping, or weight mutation is allowed."
            )

        # 2. Check token presence
        if token is None:
            raise TrainingAuthorizationError(
                "TRAINING_EXECUTION_BLOCKED: Signed training authorization token is absent. "
                "Direct CLI / shell pretraining execution is strictly forbidden."
            )

        # 3. Check expiration
        now = time.time()
        if now > token.expires_at_epoch:
            raise TrainingAuthorizationError(
                f"TRAINING_EXECUTION_BLOCKED: Signed authorization token {token.token_id} has expired."
            )

        # 4. Check cryptographic signature
        expected_sig = compute_token_signature(
            token.token_id, token.admin_public_id, token.dataset_manifest_hash, self.secret_key
        )
        if not hmac.compare_digest(token.signature_hmac, expected_sig):
            raise TrainingAuthorizationError(
                f"TRAINING_EXECUTION_BLOCKED: Invalid HMAC signature for authorization token {token.token_id}."
            )

        # 5. Check manifest hash match if supplied
        if expected_manifest_hash and token.dataset_manifest_hash != expected_manifest_hash:
            raise TrainingAuthorizationError(
                "TRAINING_EXECUTION_BLOCKED: Dataset manifest hash mismatch against authorization token."
            )

        # 6. Check required deterministic gates
        gates = {
            "rights_gate": token.rights_gate_status,
            "novelty_gate": token.novelty_gate_status,
            "provenance_gate": token.provenance_gate_status,
            "holdout_gate": token.holdout_gate_status,
            "token_accounting_gate": token.token_accounting_status,
        }
        failed_gates = [g for g, status in gates.items() if status != "PASS"]
        if failed_gates:
            raise TrainingAuthorizationError(
                f"TRAINING_EXECUTION_BLOCKED: Required governance gates failed: {failed_gates}"
            )

        # 7. Check human approval signature
        if not token.human_approval_signature or token.human_approval_signature == "UNSIGNED":
            raise TrainingAuthorizationError(
                "TRAINING_EXECUTION_BLOCKED: Human approval signature is missing or UNSIGNED."
            )

        return True
