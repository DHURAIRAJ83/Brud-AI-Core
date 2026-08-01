"""Loader/validator for `config/knowledge_routing_policy.json` (Step 15).

Structural template reused verbatim from
`backend/services/production_regression_service.py`'s
`compute_manifest_checksum`/`validate_manifest_schema`/`load_manifest`:
SHA-256 over canonical JSON with the checksum field excluded from its
own hash input, recomputed and compared on every load. The policy file
holds only inert data (keyword lexicons, version strings) -- no
executable content is ever loaded from it.
"""

from __future__ import annotations

import hashlib
import json
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from core_model.knowledge_routing import ALL_SUBDOMAINS, DOMAINS, FRESHNESS_VALUES, INTENTS

_DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "knowledge_routing_policy.json"
)

_REQUIRED_TOP_LEVEL_KEYS = (
    "policy_version", "taxonomy_version", "domains", "intents", "freshness_signals",
)

_lock = threading.Lock()


class PolicyValidationError(ValueError):
    """Raised when the policy file is missing, malformed, or checksum-mismatched."""


def compute_policy_checksum(policy: dict[str, Any]) -> str:
    payload = {k: v for k, v in policy.items() if k != "policy_checksum_sha256"}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_policy_schema(policy: dict[str, Any]) -> list[str]:
    """Pure structural validation -- returns a list of problems, empty if valid."""

    problems: list[str] = []
    for key in _REQUIRED_TOP_LEVEL_KEYS:
        if key not in policy:
            problems.append(f"missing required top-level key: {key!r}")
    if problems:
        return problems

    domains = policy["domains"]
    if not isinstance(domains, dict) or not domains:
        problems.append("'domains' must be a non-empty object")
    else:
        unknown_domains = set(domains) - set(DOMAINS)
        if unknown_domains:
            problems.append(
                f"policy declares domains not in the taxonomy: {sorted(unknown_domains)}"
            )
        for domain_key, entry in domains.items():
            if not isinstance(entry, dict):
                problems.append(f"domain {domain_key!r} entry must be an object")
                continue
            for lex_key in ("keywords_en", "keywords_ta"):
                if lex_key not in entry or not isinstance(entry[lex_key], list):
                    problems.append(f"domain {domain_key!r} missing list field {lex_key!r}")
            subdomains = entry.get("subdomains", {})
            if not isinstance(subdomains, dict):
                problems.append(f"domain {domain_key!r} 'subdomains' must be an object")
                continue
            unknown_subdomains = set(subdomains) - set(ALL_SUBDOMAINS)
            if unknown_subdomains:
                problems.append(
                    f"domain {domain_key!r} declares subdomains not in the taxonomy: "
                    f"{sorted(unknown_subdomains)}"
                )

    intents = policy.get("intents")
    if not isinstance(intents, dict) or not intents:
        problems.append("'intents' must be a non-empty object")
    else:
        unknown_intents = set(intents) - set(INTENTS)
        if unknown_intents:
            problems.append(
                f"policy declares intents not in the taxonomy: {sorted(unknown_intents)}"
            )

    freshness_signals = policy.get("freshness_signals")
    if not isinstance(freshness_signals, dict) or not freshness_signals:
        problems.append("'freshness_signals' must be a non-empty object")
    else:
        unknown_freshness = set(freshness_signals) - set(FRESHNESS_VALUES)
        if unknown_freshness:
            problems.append(
                "policy declares freshness signals not in the taxonomy: "
                f"{sorted(unknown_freshness)}"
            )

    return problems


def load_policy(policy_path: Path | None = None) -> dict[str, Any]:
    """Load, schema-validate, and checksum-verify the policy file. Fails closed."""

    path = policy_path or _DEFAULT_POLICY_PATH
    if not path.exists():
        raise PolicyValidationError(f"knowledge routing policy file not found: {path}")
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PolicyValidationError(f"knowledge routing policy is not valid JSON: {exc}") from exc

    problems = validate_policy_schema(policy)
    if problems:
        raise PolicyValidationError(
            "knowledge routing policy failed schema validation: " + "; ".join(problems)
        )

    stored_checksum = policy.get("policy_checksum_sha256")
    recomputed = compute_policy_checksum(policy)
    if stored_checksum != recomputed:
        raise PolicyValidationError(
            "knowledge routing policy checksum mismatch -- the file on disk does not match its "
            "own recorded checksum and cannot be trusted"
        )
    return policy


@lru_cache(maxsize=1)
def get_policy() -> dict[str, Any]:
    """Process-wide cached, validated policy singleton. Fails closed on invalid policy."""

    with _lock:
        return load_policy()


def reset_policy_cache() -> None:
    """Test-only: clear the cached policy singleton so a new file can be loaded."""

    get_policy.cache_clear()


__all__ = [
    "PolicyValidationError",
    "compute_policy_checksum",
    "get_policy",
    "load_policy",
    "reset_policy_cache",
    "validate_policy_schema",
]
