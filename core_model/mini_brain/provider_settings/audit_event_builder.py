"""MB-27: Audit Event Builder -- pure. Builds the exact dict the
repository inserts into `mini_brain_provider_audit_events`. Converts a
settings mutation into a list of changed field NAMES only -- never a
value, encrypted or otherwise. A secret mutation is always recorded as
`"secret:<name>"`, never `"secret:<name>=<value>"`.
"""

from __future__ import annotations

from typing import Any


def build(
    *, provider_key: str, setting_public_id: str | None, action: str,
    admin_id: str | None, changed_fields: list[str],
) -> dict[str, Any]:
    return {
        "provider_key": provider_key,
        "setting_public_id": setting_public_id,
        "action": action,
        "admin_id": admin_id,
        "changed_fields": list(changed_fields),
    }


def secret_field_name(secret_name: str) -> str:
    return f"secret:{secret_name}"
