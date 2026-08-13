"""MB-25: Plugin Manifest Loader -- pure. Validates the on-disk
package manifest shape the task spec's own Step 3 names
(`plugin.json`) -- a different, smaller shape than MB-24's own
governance manifest, since this is the shape that ships alongside the
actual code on disk. This module never reads the file itself (the
service layer does that, then passes the already-parsed dict in) --
it only validates structure.
"""

from __future__ import annotations

from typing import Any

REQUIRED_STRING_FIELDS = ("plugin_id", "name", "version", "entrypoint", "description")
MAX_STRING_FIELD_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 2000
MAX_PERMISSIONS = 20


def validate_package_manifest(*, manifest: dict[str, Any]) -> dict[str, Any]:
    problems: list[str] = []

    for field in REQUIRED_STRING_FIELDS:
        value = manifest.get(field)
        if not isinstance(value, str):
            problems.append(f"{field} must be a string")
            continue
        limit = MAX_DESCRIPTION_LENGTH if field == "description" else MAX_STRING_FIELD_LENGTH
        if len(value) > limit:
            problems.append(f"{field} exceeds maximum length of {limit} characters")
        if field in ("plugin_id", "name", "version", "entrypoint") and not value.strip():
            problems.append(f"{field} must not be blank")

    permissions = manifest.get("permissions")
    if not isinstance(permissions, list):
        problems.append("permissions must be a list")
    elif len(permissions) > MAX_PERMISSIONS:
        problems.append(f"permissions exceeds maximum of {MAX_PERMISSIONS} entries")
    elif not all(isinstance(scope, str) for scope in permissions):
        problems.append("every entry in permissions must be a string")

    for field in ("public_chat_enabled", "admin_assistant_enabled"):
        if not isinstance(manifest.get(field), bool):
            problems.append(f"{field} must be a boolean")

    entrypoint = manifest.get("entrypoint")
    if isinstance(entrypoint, str) and entrypoint and not entrypoint.endswith(".py"):
        problems.append("entrypoint must be a .py file")

    return {
        "valid": not problems, "problems": problems,
        "disclosure": "strict, deterministic structural validation only -- this never verifies the plugin's actual code behavior",
    }
