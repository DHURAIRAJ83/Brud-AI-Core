"""MB-24: Plugin Trust Evaluator -- pure. Presence checks on a
manifest's own declared metadata (homepage, support_url, author,
signature_placeholder) -- never a security guarantee, and
`signature_verified` is always `False` since no cryptographic
signature verification exists anywhere in this phase.
"""

from __future__ import annotations

from typing import Any

MAX_TRUST_SCORE = 4


def evaluate_trust_signals(*, manifest: dict[str, Any]) -> dict[str, Any]:
    signals = {
        "has_homepage": bool(str(manifest.get("homepage", "")).strip()),
        "has_support_url": bool(str(manifest.get("support_url", "")).strip()),
        "has_author": bool(str(manifest.get("author", "")).strip()),
        "has_signature_placeholder": bool(str(manifest.get("signature_placeholder", "")).strip()),
        "signature_verified": False,
    }
    trust_score = sum(1 for key, value in signals.items() if value and key != "signature_verified")

    return {
        "signals": signals, "trust_score": trust_score, "max_trust_score": MAX_TRUST_SCORE,
        "disclosure": (
            "presence checks on declared metadata only -- signature_placeholder is never "
            "cryptographically verified, and none of this is a security guarantee"
        ),
    }
