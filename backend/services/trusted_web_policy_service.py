"""Phase 20 Step 5 -- versioned, checksum-verified, fail-closed source
trust policy loader. Mirrors `production_regression_service.py`'s own
`compute_manifest_checksum()`/`load_manifest()` pattern exactly: the
checksum is a SHA-256 over the sorted-key, compact-JSON payload minus
the checksum field itself, and any mismatch (or missing/malformed
file) raises rather than silently falling back to an empty or
permissive policy -- an untrusted policy file must never be treated
as "no restrictions."

Reloadable only through `TrustedWebAdminService` (Admin-governed), not
a raw public or unauthenticated upload endpoint.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.database.repositories.base import NotFoundError, ValidationError
from core_model.web_search import SOURCE_TRUST_LEVELS, WEB_QUERY_CATEGORIES

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "trusted_web_policy.json"

_REQUIRED_POLICY_KEYS = (
    "policy_version",
    "allowed_domains",
    "blocked_domains",
    "official_source_patterns",
    "source_category_rules",
    "fetch_allowed",
    "snippet_only_allowed",
    "required_verification_level",
    "freshness_thresholds",
    "maximum_results",
    "maximum_fetches",
    "timeouts",
    "content_limits",
    "provider_priority",
    "policy_checksum_sha256",
)


def compute_policy_checksum(policy: dict[str, Any]) -> str:
    payload = {k: v for k, v in policy.items() if k != "policy_checksum_sha256"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_policy_schema(policy: dict[str, Any]) -> list[str]:
    """Pure structural validation -- returns a list of problems, empty if valid."""

    problems: list[str] = []
    for key in _REQUIRED_POLICY_KEYS:
        if key not in policy:
            problems.append(f"missing required key: {key}")
    if problems:
        return problems

    if not isinstance(policy["allowed_domains"], dict):
        problems.append("allowed_domains must be an object mapping domain -> trust level")
    else:
        for domain, level in policy["allowed_domains"].items():
            if level not in SOURCE_TRUST_LEVELS:
                problems.append(f"allowed_domains[{domain!r}] has unknown trust level: {level!r}")

    if not isinstance(policy["blocked_domains"], list):
        problems.append("blocked_domains must be a list")

    for category in policy.get("source_category_rules", {}):
        if category not in WEB_QUERY_CATEGORIES:
            problems.append(f"source_category_rules has unknown category: {category!r}")

    for level in policy.get("fetch_allowed", []):
        if level not in SOURCE_TRUST_LEVELS:
            problems.append(f"fetch_allowed has unknown trust level: {level!r}")

    for value in (policy.get("maximum_results"), policy.get("maximum_fetches")):
        if not isinstance(value, int) or value <= 0:
            problems.append("maximum_results/maximum_fetches must be positive integers")

    return problems


@lru_cache(maxsize=4)
def _load_policy_cached(path_str: str, mtime_ns: int) -> dict[str, Any]:
    """`mtime_ns` is part of the cache key purely to auto-invalidate
    when the on-disk file changes (e.g. after an Admin-governed
    reload) -- never a manual cache-clear call scattered through the
    codebase."""

    path = Path(path_str)
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"trusted Web policy is not valid JSON: {exc}") from exc

    problems = validate_policy_schema(policy)
    if problems:
        raise ValidationError("trusted Web policy failed schema validation: " + "; ".join(problems))
    stored_checksum = policy.get("policy_checksum_sha256")
    recomputed = compute_policy_checksum(policy)
    if stored_checksum != recomputed:
        raise ValidationError(
            "trusted Web policy checksum mismatch -- the file on disk does not match its own "
            "recorded checksum and cannot be trusted"
        )
    return policy


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, Any]:
    if not path.exists():
        raise NotFoundError(f"trusted Web policy file not found: {path}")
    mtime_ns = path.stat().st_mtime_ns
    return _load_policy_cached(str(path), mtime_ns)


def domain_trust_level(policy: dict[str, Any], domain: str) -> str:
    domain = domain.lower()
    if domain in policy["blocked_domains"]:
        return "blocked"
    allowed = policy["allowed_domains"]
    if domain in allowed:
        return allowed[domain]
    for pattern in policy["official_source_patterns"]:
        suffix = pattern.lstrip("*")
        if domain.endswith(suffix):
            return "official"
    return "unknown"


def category_rule(policy: dict[str, Any], category: str) -> dict[str, Any]:
    return policy["source_category_rules"].get(
        category,
        {
            "preferred_trust_levels": ["official", "authoritative"],
            "min_verification_level": "content_verified",
        },
    )


__all__ = [
    "DEFAULT_POLICY_PATH",
    "category_rule",
    "compute_policy_checksum",
    "domain_trust_level",
    "load_policy",
    "validate_policy_schema",
]
