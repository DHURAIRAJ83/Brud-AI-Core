"""Release-manifest checksum and sensitive-content scanning.

Manifest *assembly* happens in the service layer (which has access to the
registered rows) — this module only computes the deterministic checksum
and defensively scans the assembled manifest for content that must never
appear in it (absolute paths, secret-shaped values, numeric database IDs).
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from backend.core.json_utils import dumps_json

_ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|[\s\"])(?:/home/|/etc/|/usr/|/var/|[A-Za-z]:\\\\)\S*")
_SECRET_LIKE_PATTERN = re.compile(
    r"\b(api[_-]?key|password|secret|token)\s*[:=]\s*\S+", re.IGNORECASE
)

REQUIRED_MANIFEST_FIELDS = (
    "release_family_public_id", "candidate_public_id", "core_model_version_public_id",
    "checkpoint_public_id", "checkpoint_checksum_sha256", "model_config_checksum_sha256",
    "parameter_count", "context_length", "tokenizer_version_public_id",
    "tokenizer_checksums", "dataset_versions", "base_training_manifest_checksum_sha256",
    "instruction_tuning_manifest_checksum_sha256", "evaluation_manifest_checksum_sha256",
    "evaluation_readiness_status", "model_card_checksum_sha256", "licence_notices",
    "compatibility_assessment", "eligibility_assessment", "approvals",
    "resource_requirements", "supported_languages", "known_limitations",
    "software_versions", "created_at",
)


def manifest_checksum(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(dumps_json(manifest).encode("utf-8")).hexdigest()


def verify_manifest_checksum(manifest_json: str, stored_checksum: str) -> bool:
    return hashlib.sha256(manifest_json.encode("utf-8")).hexdigest() == stored_checksum


def scan_for_sensitive_content(manifest: dict[str, Any]) -> list[str]:
    """Returns a list of concerns found — empty means the manifest is clean."""

    concerns: list[str] = []
    serialized = dumps_json(manifest).replace("\\/", "/")
    if _ABSOLUTE_PATH_PATTERN.search(serialized):
        concerns.append("absolute_path_detected")
    if _SECRET_LIKE_PATTERN.search(serialized):
        concerns.append("secret_like_content_detected")
    return sorted(set(concerns))


def missing_required_fields(manifest: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_MANIFEST_FIELDS if field not in manifest]
