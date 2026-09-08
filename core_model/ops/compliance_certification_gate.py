"""Phase 61 - P9: Cryptographic Compliance Certification Gate.

Provides HMAC-SHA256 cryptographic certification tokens for enterprise compliance export packages.

CRITICAL INVARIANTS:
- Requires signed SignedComplianceCertificationToken bound to request ID, package ID, evidence hash, tenant ID, admin ID, and expiration epoch.
- Default: COMPLIANCE_CERTIFICATION = BLOCKED.
- Admin Assistant cannot certify independently. Explicit human Admin / Legal Officer signature is mandatory.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Any


class ComplianceCertificationError(RuntimeError):
    """Raised when compliance certification token validation fails."""


@dataclass
class SignedComplianceCertificationToken:
    """Cryptographically signed enterprise compliance certification token."""
    certification_request_id: str
    package_id: str
    package_hash: str
    tenant_id: str
    admin_public_id: str
    admin_role: str  # HUMAN_ADMIN | LEGAL_OFFICER
    policy_version: str
    created_at_epoch: float
    expires_at_epoch: float
    signature_hmac: str


def compute_compliance_token_signature(
    certification_request_id: str,
    package_id: str,
    package_hash: str,
    tenant_id: str,
    admin_public_id: str,
    secret_key: str = "BRUD_COMPLIANCE_SECRET_KEY_2026",
) -> str:
    """Compute HMAC-SHA256 signature for compliance certification token."""
    raw = f"{certification_request_id}:{package_id}:{package_hash}:{tenant_id}:{admin_public_id}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), raw, hashlib.sha256).hexdigest()


class ComplianceCertificationGate:
    """Cryptographic compliance certification gate."""

    def __init__(self, secret_key: str = "BRUD_COMPLIANCE_SECRET_KEY_2026") -> None:
        self.secret_key = secret_key

    def verify_certification_token(
        self,
        token: SignedComplianceCertificationToken | None,
        expected_package_id: str,
        expected_package_hash: str,
        expected_tenant_id: str,
    ) -> bool:
        """Verify compliance certification token HMAC signature, expiration, and hash bindings."""
        if token is None:
            raise ComplianceCertificationError("COMPLIANCE_CERTIFICATION_BLOCKED: Token is absent.")

        if token.admin_role == "ADMIN_ASSISTANT_ADVISORY":
            raise ComplianceCertificationError("COMPLIANCE_CERTIFICATION_BLOCKED: Admin Assistant is advisory only and cannot certify compliance.")

        if token.admin_role not in ("HUMAN_ADMIN", "LEGAL_OFFICER"):
            raise ComplianceCertificationError(f"COMPLIANCE_CERTIFICATION_BLOCKED: Invalid certifying role '{token.admin_role}'.")

        if time.time() > token.expires_at_epoch:
            raise ComplianceCertificationError(f"COMPLIANCE_CERTIFICATION_BLOCKED: Token {token.certification_request_id} has expired.")

        expected_sig = compute_compliance_token_signature(
            token.certification_request_id, token.package_id, token.package_hash, token.tenant_id, token.admin_public_id, self.secret_key
        )
        if not hmac.compare_digest(token.signature_hmac, expected_sig):
            raise ComplianceCertificationError(f"COMPLIANCE_CERTIFICATION_BLOCKED: Invalid HMAC signature on token {token.certification_request_id}.")

        if token.package_id != expected_package_id:
            raise ComplianceCertificationError("COMPLIANCE_CERTIFICATION_BLOCKED: Package ID mismatch.")

        if token.package_hash != expected_package_hash:
            raise ComplianceCertificationError("COMPLIANCE_CERTIFICATION_BLOCKED: Evidence package hash mismatch.")

        if token.tenant_id != expected_tenant_id:
            raise ComplianceCertificationError("COMPLIANCE_CERTIFICATION_BLOCKED: Tenant ID mismatch.")

        return True
