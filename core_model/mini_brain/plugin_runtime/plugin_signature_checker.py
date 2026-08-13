"""MB-25: Plugin Signature Checker -- pure. Compares an already-
computed file checksum (the service layer computes it via the same
`core_model.release.artifact_inventory.file_checksum()` MB-18 through
MB-24 already share) against the checksum MB-24 recorded at approval
time. This never performs cryptographic signature verification --
`signature_placeholder` is a presence check only, exactly matching
MB-24's own honest disclosure.
"""

from __future__ import annotations

from typing import Any


def verify_checksum(*, expected_checksum_sha256: str | None, actual_checksum_sha256: str) -> dict[str, Any]:
    if not expected_checksum_sha256:
        return {"verified": False, "matches": None, "reason": "no expected checksum was declared at approval time"}
    matches = expected_checksum_sha256 == actual_checksum_sha256
    return {"verified": matches, "matches": matches, "reason": None if matches else "on-disk file checksum does not match the checksum MB-24 approved"}


def evaluate_signature_trust(*, signature_placeholder: str, checksum_verified: bool) -> dict[str, Any]:
    return {
        "signature_present": bool(signature_placeholder.strip()), "signature_cryptographically_verified": False,
        "checksum_verified": checksum_verified,
        "disclosure": (
            "no cryptographic signature verification exists in this phase -- signature_placeholder is a "
            "presence check only, and a matching checksum only proves the on-disk file is byte-identical "
            "to what MB-24 originally approved, not that the code itself is safe"
        ),
    }
