"""MB-27: Settings Import Validator -- pure. Validates an import
payload against the same whitelist-of-fields shape
`settings_export_builder.py` produces -- rejects any payload
containing extra/unexpected keys (defense against smuggling
`encrypted_value` or any secret-shaped field back in via import), and
rejects unknown provider_keys via the registry.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.provider_settings.provider_registry import is_known_provider

_ALLOWED_PROVIDER_ENTRY_FIELDS = frozenset({"provider_key", "provider_type", "enabled", "config", "updated_at"})
_FORBIDDEN_FIELDS = frozenset({"encrypted_value", "value", "api_key", "secret_value", "plaintext_value", "secrets"})


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    providers = payload.get("providers")
    if not isinstance(providers, list):
        return {"valid": False, "errors": ["payload must contain a 'providers' list"], "providers": []}

    validated: list[dict[str, Any]] = []
    for index, entry in enumerate(providers):
        if not isinstance(entry, dict):
            errors.append(f"providers[{index}] must be an object")
            continue
        forbidden_present = _FORBIDDEN_FIELDS & set(entry.keys())
        if forbidden_present:
            errors.append(f"providers[{index}] contains forbidden field(s): {sorted(forbidden_present)}")
            continue
        unexpected = set(entry.keys()) - _ALLOWED_PROVIDER_ENTRY_FIELDS
        if unexpected:
            errors.append(f"providers[{index}] contains unexpected field(s): {sorted(unexpected)}")
            continue
        provider_key = entry.get("provider_key")
        if not is_known_provider(provider_key):
            errors.append(f"providers[{index}] has unknown provider_key: {provider_key!r}")
            continue
        validated.append(entry)

    return {"valid": len(errors) == 0, "errors": errors, "providers": validated}
