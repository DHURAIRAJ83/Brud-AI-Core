"""MB-24: Network Policy Builder -- pure. Builds a declarative,
normalized network policy from a plugin's own declared domains --
policy metadata only. No HTTP request, DNS lookup, or socket is ever
opened by this module.
"""

from __future__ import annotations

from typing import Any


def build_network_policy(*, network_enabled: bool, allowed_domains: list[str]) -> dict[str, Any]:
    domains = sorted({domain.lower().strip() for domain in allowed_domains if domain.strip()}) if network_enabled else []
    return {
        "network_enabled": network_enabled, "allowed_domains": domains, "domain_count": len(domains),
        "wildcard_domains_present": any(domain.startswith("*") for domain in domains),
        "disclosure": "declarative policy metadata only -- enforcement requires a real runtime this phase does not implement, and no network request is ever made by this module",
    }
