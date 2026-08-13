"""MB-24: Plugin Marketplace Policy -- pure. MB-24 is explicitly not a
marketplace frontend, not a deployment engine, and not a plugin
auto-installer. This module encodes that as an enforceable policy
result rather than only a comment: `auto_install_permitted` and
`auto_enable_permitted` are always `False`, and every plugin requires
manual admin registration regardless of its declared source.
"""

from __future__ import annotations

from typing import Any

ALLOWED_SOURCES = ("manual_upload", "local_development", "marketplace_reference")


def evaluate_marketplace_policy(*, source: str) -> dict[str, Any]:
    if source not in ALLOWED_SOURCES:
        return {
            "allowed": False, "reason": f"unknown plugin source: {source!r}",
            "auto_install_permitted": False, "auto_enable_permitted": False,
            "requires_manual_admin_registration": True,
        }
    return {
        "allowed": True, "reason": None, "auto_install_permitted": False, "auto_enable_permitted": False,
        "requires_manual_admin_registration": True,
        "disclosure": (
            "MB-24 is not a marketplace frontend or auto-installer -- auto_install_permitted and "
            "auto_enable_permitted are always False for every source; every plugin must be manually "
            "registered and manually enabled by an admin"
        ),
    }
