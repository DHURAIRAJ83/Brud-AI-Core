"""MB-25: Network Guard -- pure. Deterministic domain-allowlist
matching against MB-24's own already-approved `allowed_domains` (the
task spec's own Step 11). Exact match or a leading `*.` wildcard
subdomain match only -- no regex, no partial-substring matching. This
module never opens a socket or makes an HTTP request.
"""

from __future__ import annotations

from typing import Any


def check_domain_allowed(*, requested_domain: str, allowed_domains: list[str]) -> dict[str, Any]:
    normalized_requested = requested_domain.lower().strip()
    normalized_allowed = [domain.lower().strip() for domain in allowed_domains]

    if normalized_requested in normalized_allowed:
        return {"allowed": True, "reason": None, "matched_domain": normalized_requested}

    for domain in normalized_allowed:
        if domain.startswith("*.") and normalized_requested.endswith(domain[1:]):
            return {"allowed": True, "reason": None, "matched_domain": domain}

    return {
        "allowed": False, "matched_domain": None,
        "reason": f"domain '{requested_domain}' is not in the approved allowed_domains list",
    }
