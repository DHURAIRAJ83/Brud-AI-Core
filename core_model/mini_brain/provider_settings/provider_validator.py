"""MB-27: Provider Validator -- pure. Validates a provider_key against
the registry, checks whether a set of already-present secret names
satisfies a provider's required_secrets, and checks a config dict's
keys against the provider's declared optional_settings -- never
inspects secret values themselves, only names/presence.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.provider_settings.provider_registry import (
    is_known_provider,
    provider_definition,
)


def validate_provider_key(provider_key: str) -> dict[str, Any]:
    if not is_known_provider(provider_key):
        return {"valid": False, "errors": [f"unknown provider_key: {provider_key!r}"]}
    return {"valid": True, "errors": []}


def validate_config(*, provider_key: str, config: dict[str, Any]) -> dict[str, Any]:
    definition = provider_definition(provider_key)
    if definition is None:
        return {"valid": False, "errors": [f"unknown provider_key: {provider_key!r}"]}
    allowed_keys = set(definition["optional_settings"].keys())
    unexpected = sorted(set(config.keys()) - allowed_keys)
    if unexpected:
        return {"valid": False, "errors": [f"unexpected config key(s): {unexpected}"]}
    return {"valid": True, "errors": []}


def missing_required_secrets(*, provider_key: str, present_secret_names: list[str]) -> list[str]:
    definition = provider_definition(provider_key)
    if definition is None:
        return []
    present = set(present_secret_names)
    return [name for name in definition["required_secrets"] if name not in present]


def is_fully_configured(*, provider_key: str, present_secret_names: list[str]) -> bool:
    return len(missing_required_secrets(provider_key=provider_key, present_secret_names=present_secret_names)) == 0
