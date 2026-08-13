"""MB-25: Consent Gate -- pure. The execution-time check that a
consent-requiring scope has a currently-valid consent record --
validity (including expiry) is computed by the caller via MB-24's own
`consent_policy_engine.is_consent_valid()`; this module only enforces
the gate given that already-computed boolean.
"""

from __future__ import annotations

from typing import Any


def evaluate_execution_consent(*, required_scope: str, consent_required: bool, has_valid_consent: bool) -> dict[str, Any]:
    if not consent_required:
        return {"allowed": True, "reason": None}
    if has_valid_consent:
        return {"allowed": True, "reason": None}
    return {"allowed": False, "reason": f"scope '{required_scope}' requires valid, unexpired user consent"}
