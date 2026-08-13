"""MB-24: Plugin Manifest Validator -- pure. Strictly validates the
deterministic JSON manifest shape the task spec's own Step 9 names.
Every bound here exists to satisfy Step 19's performance constraints
(bounded manifest size, bounded allowed-domain list) -- an oversized
or malformed manifest is rejected before any other stage ever sees it.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.plugin_governance.permission_scope_registry import is_known_scope

REQUIRED_STRING_FIELDS = (
    "plugin_id", "name", "version", "author", "description", "entrypoint",
    "minimum_brud_version", "signature_placeholder", "homepage", "support_url",
)
REQUIRED_LIST_FIELDS = ("requested_scopes", "allowed_domains", "filesystem_roots", "ui_components")
REQUIRED_BOOL_FIELDS = ("local_storage_usage", "cloud_storage_usage")

MAX_STRING_FIELD_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 2000
MAX_SCOPES = 20
MAX_ALLOWED_DOMAINS = 20
MAX_FILESYSTEM_ROOTS = 10
MAX_UI_COMPONENTS = 20
MAX_DOMAIN_LENGTH = 253


def _string_field_problems(manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for field in REQUIRED_STRING_FIELDS:
        value = manifest.get(field)
        if not isinstance(value, str):
            problems.append(f"{field} must be a string")
            continue
        limit = MAX_DESCRIPTION_LENGTH if field == "description" else MAX_STRING_FIELD_LENGTH
        if len(value) > limit:
            problems.append(f"{field} exceeds maximum length of {limit} characters")
    for field in ("plugin_id", "name", "version", "entrypoint"):
        value = manifest.get(field)
        if isinstance(value, str) and not value.strip():
            problems.append(f"{field} must not be blank")
    return problems


def _list_field_problems(manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for field in REQUIRED_LIST_FIELDS:
        value = manifest.get(field)
        if not isinstance(value, list):
            problems.append(f"{field} must be a list")
    return problems


def _bool_field_problems(manifest: dict[str, Any]) -> list[str]:
    return [f"{field} must be a boolean" for field in REQUIRED_BOOL_FIELDS if not isinstance(manifest.get(field), bool)]


def _scope_problems(manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    scopes = manifest.get("requested_scopes")
    if not isinstance(scopes, list):
        return problems
    if len(scopes) > MAX_SCOPES:
        problems.append(f"requested_scopes exceeds maximum of {MAX_SCOPES} entries")
    for scope in scopes:
        if not isinstance(scope, str) or not is_known_scope(scope):
            problems.append(f"unknown or invalid scope: {scope!r}")
    return problems


def _domain_problems(manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    domains = manifest.get("allowed_domains")
    if not isinstance(domains, list):
        return problems
    if len(domains) > MAX_ALLOWED_DOMAINS:
        problems.append(f"allowed_domains exceeds maximum of {MAX_ALLOWED_DOMAINS} entries")
    for domain in domains:
        if not isinstance(domain, str) or not domain.strip() or len(domain) > MAX_DOMAIN_LENGTH:
            problems.append(f"invalid domain entry: {domain!r}")
    return problems


def _bounded_list_problems(manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    roots = manifest.get("filesystem_roots")
    if isinstance(roots, list) and len(roots) > MAX_FILESYSTEM_ROOTS:
        problems.append(f"filesystem_roots exceeds maximum of {MAX_FILESYSTEM_ROOTS} entries")
    components = manifest.get("ui_components")
    if isinstance(components, list) and len(components) > MAX_UI_COMPONENTS:
        problems.append(f"ui_components exceeds maximum of {MAX_UI_COMPONENTS} entries")
    return problems


def validate_manifest(*, manifest: dict[str, Any]) -> dict[str, Any]:
    all_fields = REQUIRED_STRING_FIELDS + REQUIRED_LIST_FIELDS + REQUIRED_BOOL_FIELDS
    missing = [field for field in all_fields if field not in manifest]
    problems: list[str] = [f"missing required field: {field}" for field in missing]

    if not missing:
        problems.extend(_string_field_problems(manifest))
        problems.extend(_list_field_problems(manifest))
        problems.extend(_bool_field_problems(manifest))
        problems.extend(_scope_problems(manifest))
        problems.extend(_domain_problems(manifest))
        problems.extend(_bounded_list_problems(manifest))

    return {
        "valid": not problems, "problems": problems,
        "field_count": len(manifest), "requested_scope_count": len(manifest.get("requested_scopes", []) or []),
        "disclosure": "strict, deterministic structural validation only -- this never verifies a plugin's signature or behavior",
    }
