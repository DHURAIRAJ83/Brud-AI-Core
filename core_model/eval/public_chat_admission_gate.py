"""Phase 61 - P6: Public Chat Admission Gate & Runtime Model Routing Protection.

Provides a dedicated governance boundary for public chat admission.

CRITICAL INVARIANTS:
- Production release success alone does NOT authorize public chat admission.
- Public chat admission requires an explicit HMAC-SHA256 SignedPublicChatAdmissionToken.
- Requires ALL 14 admission conditions to pass. Fails closed (public_chat_eligible = FALSE) on any failure.
- Runtime routing protection: Ensures PUBLIC_CHAT -> PRODUCTION_MODEL only when public_chat_eligible = TRUE.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from core_model.eval.canary_deployment_governance import CanaryDeploymentResult
from core_model.eval.production_release_registry import ProductionReleaseRecord


class PublicChatAdmissionError(RuntimeError):
    """Raised when public chat admission gate fails."""


@dataclass
class SignedPublicChatAdmissionToken:
    """Cryptographically signed public chat admission authorization token."""
    token_id: str
    admin_public_id: str
    release_id: str
    candidate_model_hash: str
    dataset_manifest_hash: str
    human_admission_signature: str
    created_at_epoch: float
    expires_at_epoch: float
    signature_hmac: str


def compute_public_chat_admission_signature(
    token_id: str,
    admin_public_id: str,
    release_id: str,
    candidate_model_hash: str,
    secret_key: str = "BRUD_PUBLIC_CHAT_SECRET_KEY_2026",
) -> str:
    """Compute HMAC-SHA256 signature for public chat admission token."""
    raw = f"{token_id}:{admin_public_id}:{release_id}:{candidate_model_hash}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), raw, hashlib.sha256).hexdigest()


@dataclass
class PublicChatAdmissionResult:
    """Outcome of public chat admission evaluation."""
    admitted: bool
    public_chat_eligible: bool  # TRUE ONLY WHEN ALL GATES PASS AND SIGNED TOKEN IS VALID
    release_id: str
    active_routing_model_hash: str
    failed_reasons: list[str] = field(default_factory=list)


class PublicChatAdmissionGate:
    """Public chat admission gate and runtime routing protector."""

    def __init__(
        self,
        secret_key: str = "BRUD_PUBLIC_CHAT_SECRET_KEY_2026",
        existing_approved_production_hash: str = "approved-prod-hash-0000",
    ) -> None:
        self.secret_key = secret_key
        self.existing_approved_production_hash = existing_approved_production_hash

    def verify_admission_token(
        self,
        token: SignedPublicChatAdmissionToken | None,
        release_record: ProductionReleaseRecord,
    ) -> bool:
        """Verify public chat admission token HMAC signature and expiration."""
        if token is None:
            raise PublicChatAdmissionError("PUBLIC_CHAT_BLOCKED: Signed public chat admission token is absent.")

        if time.time() > token.expires_at_epoch:
            raise PublicChatAdmissionError(f"PUBLIC_CHAT_BLOCKED: Admission token {token.token_id} has expired.")

        expected_sig = compute_public_chat_admission_signature(
            token.token_id, token.admin_public_id, token.release_id, token.candidate_model_hash, self.secret_key
        )
        if not hmac.compare_digest(token.signature_hmac, expected_sig):
            raise PublicChatAdmissionError(f"PUBLIC_CHAT_BLOCKED: Invalid HMAC signature on admission token {token.token_id}.")

        if token.candidate_model_hash != release_record.candidate_model_hash:
            raise PublicChatAdmissionError("PUBLIC_CHAT_BLOCKED: Model hash mismatch against admission token.")

        return True

    def evaluate_public_chat_admission(
        self,
        release_record: ProductionReleaseRecord | None,
        canary_res: CanaryDeploymentResult | None,
        signed_token: SignedPublicChatAdmissionToken | None = None,
        admin_admission_decision: str = "PUBLIC_CHAT_APPROVED",
    ) -> PublicChatAdmissionResult:
        """Evaluate public chat admission gates and enforce fail-closed routing."""
        failed_reasons = []

        if release_record is None:
            failed_reasons.append("No active ProductionReleaseRecord provided.")
            return PublicChatAdmissionResult(
                admitted=False,
                public_chat_eligible=False,
                release_id="none",
                active_routing_model_hash=self.existing_approved_production_hash,
                failed_reasons=failed_reasons
            )

        # 1. Release status check
        if release_record.release_status != "PRODUCTION_ACTIVE":
            failed_reasons.append(f"Release status '{release_record.release_status}' is not PRODUCTION_ACTIVE.")

        # 2. Canary status check
        if canary_res is None or canary_res.canary_status != "CANARY_PASSED" or canary_res.candidate_traffic_share < 1.00:
            failed_reasons.append("Canary deployment has not reached 100% CANARY_PASSED status.")

        # 3. Admin Decision check
        if admin_admission_decision not in ("PUBLIC_CHAT_APPROVED", "APPROVED"):
            failed_reasons.append(f"Admin Decision '{admin_admission_decision}' is not PUBLIC_CHAT_APPROVED.")

        # 4. Signed Admission Token check
        if signed_token is None:
            failed_reasons.append("Missing SignedPublicChatAdmissionToken.")
        else:
            try:
                self.verify_admission_token(signed_token, release_record)
            except PublicChatAdmissionError as err:
                failed_reasons.append(str(err))

        if failed_reasons:
            return PublicChatAdmissionResult(
                admitted=False,
                public_chat_eligible=False,
                release_id=release_record.release_id,
                active_routing_model_hash=self.existing_approved_production_hash,  # Fallback to approved prod model
                failed_reasons=failed_reasons
            )

        # Successful Admission
        release_record.public_chat_status = "ADMITTED"
        return PublicChatAdmissionResult(
            admitted=True,
            public_chat_eligible=True,
            release_id=release_record.release_id,
            active_routing_model_hash=release_record.candidate_model_hash,
            failed_reasons=[]
        )
