"""MB-21: Request Policy -- pure. Enforces the task spec's own non-
negotiable ordering rule: no provider call is ever allowed before an
explicit admin authorization is on record for this exact session.
This module never grants authorization itself -- it only validates
that a real admin identity and a non-empty justification were
supplied.
"""

from __future__ import annotations

from typing import Any

VALID_PURPOSES = ("public_style_stress_test", "data_acquisition_assistance")


def validate_authorization(
    *, admin_public_id: str | None, authorization_note: str, purpose: str,
) -> dict[str, Any]:
    reasons: list[str] = []
    if not admin_public_id:
        reasons.append("no admin identity was supplied -- authorization requires a real, specific admin")
    if not authorization_note.strip():
        reasons.append("authorization_note must not be empty -- a stated reason is required for every provider call")
    if purpose not in VALID_PURPOSES:
        reasons.append(f"purpose must be one of {list(VALID_PURPOSES)}")

    authorized = not reasons
    return {
        "authorized": authorized, "reasons": reasons, "admin_public_id": admin_public_id if authorized else None,
        "purpose": purpose,
        "disclosure": (
            "authorization here only proves an admin identity and a stated reason were recorded on "
            "this exact session -- it never grants approval for any downstream dataset, release, or "
            "training decision"
        ),
    }
