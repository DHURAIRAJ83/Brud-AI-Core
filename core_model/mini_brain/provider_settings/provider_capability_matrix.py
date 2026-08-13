"""MB-27: Provider Capability Matrix -- pure projection of
`capability_flags` from the registry. Not a second source of truth --
a thin, pure reshaping function.
"""

from __future__ import annotations

from core_model.mini_brain.provider_settings.provider_registry import PROVIDER_REGISTRY, provider_definition


def capabilities_for(provider_key: str) -> dict[str, bool]:
    definition = provider_definition(provider_key)
    if definition is None:
        return {}
    return dict(definition["capability_flags"])


def full_matrix() -> dict[str, dict[str, bool]]:
    return {key: dict(value["capability_flags"]) for key, value in PROVIDER_REGISTRY.items()}
