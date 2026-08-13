"""MB-27: Provider Health Summary -- pure. Given a provider's enabled
flag, whether its required secrets are present (booleans only, never
the secrets themselves), and its most recent connection-test result
(if any), computes a health verdict.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.provider_settings.provider_validator import missing_required_secrets

_HEALTHY_TEST_STATUSES = frozenset({"success"})


def summarize(
    *, provider_key: str, enabled: bool, present_secret_names: list[str],
    last_test_status: str | None = None,
) -> dict[str, Any]:
    missing = missing_required_secrets(provider_key=provider_key, present_secret_names=present_secret_names)

    if not enabled:
        return {"provider_key": provider_key, "health": "disabled", "reason": "provider is not enabled"}
    if missing:
        return {
            "provider_key": provider_key, "health": "unconfigured",
            "reason": f"missing required secret(s): {missing}",
        }
    if last_test_status is not None and last_test_status not in _HEALTHY_TEST_STATUSES:
        return {
            "provider_key": provider_key, "health": "degraded",
            "reason": f"last connection test reported status={last_test_status!r}",
        }
    return {"provider_key": provider_key, "health": "healthy", "reason": None}
