"""Safe release-bundle content decisions.

This module decides *what* goes into a bundle and validates it — it never
writes the archive itself (that filesystem operation lives in the service
layer, the same split the project uses elsewhere between pure decision
logic and I/O). A bundle is only ever built from already-verified
registered artifacts, and generation for a blocked candidate must be
rejected before any archive is written.
"""

from __future__ import annotations

import hashlib
from typing import Any

from backend.core.json_utils import dumps_json

BUNDLE_REQUIRED_ENTRIES = (
    "model/checkpoint",
    "model/config.json",
    "tokenizer/tokenizer.model",
    "tokenizer/tokenizer.vocab",
    "tokenizer/tokenizer_manifest.json",
    "manifests/release_manifest.json",
    "manifests/training_manifest.json",
    "manifests/evaluation_manifest.json",
    "model_card.md",
    "LICENCE",
    "CHECKSUMS.sha256",
    "README.md",
)

_FORBIDDEN_PATH_FRAGMENTS = (
    ".env", ".db", ".sqlite", "session", "admin_accounts", ".git/", "__pycache__",
)

_ARTIFACT_TYPE_TO_BUNDLE_PATH = {
    "model_checkpoint": "model/checkpoint",
    "model_config": "model/config.json",
    "tokenizer_model": "tokenizer/tokenizer.model",
    "tokenizer_vocab": "tokenizer/tokenizer.vocab",
    "tokenizer_manifest": "tokenizer/tokenizer_manifest.json",
    "base_training_manifest": "manifests/training_manifest.json",
    "instruction_tuning_manifest": "manifests/instruction_manifest.json",
    "evaluation_manifest": "manifests/evaluation_manifest.json",
    "release_manifest": "manifests/release_manifest.json",
    "model_card": "model_card.md",
    "licence_notice": "LICENCE",
}


def validate_bundle_source_artifacts(
    artifacts: list[dict[str, Any]], *, instruction_tuned: bool
) -> list[str]:
    """Returns missing/invalid artifact-type problems; empty means ready to bundle."""

    by_type = {artifact["artifact_type"]: artifact for artifact in artifacts}
    required_types = [
        "model_checkpoint", "model_config", "tokenizer_model", "tokenizer_vocab",
        "tokenizer_manifest", "base_training_manifest", "evaluation_manifest",
        "model_card", "release_manifest", "licence_notice",
    ]
    if instruction_tuned:
        required_types.append("instruction_tuning_manifest")
    problems = []
    for artifact_type in required_types:
        artifact = by_type.get(artifact_type)
        if artifact is None or artifact.get("verification_status") != "verified":
            problems.append(artifact_type)
    return problems


def build_bundle_inventory(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deterministic, sorted inventory — excludes any artifact type without a
    defined bundle path (nothing outside the fixed, documented layout)."""

    inventory = []
    for artifact in artifacts:
        bundle_path = _ARTIFACT_TYPE_TO_BUNDLE_PATH.get(artifact["artifact_type"])
        if bundle_path is None:
            continue
        inventory.append({
            "path": bundle_path,
            "checksum": artifact["checksum"],
            "size_bytes": artifact["size_bytes"],
        })
    return sorted(inventory, key=lambda entry: entry["path"])


def scan_bundle_paths_for_forbidden_content(paths: list[str]) -> list[str]:
    findings = []
    for path in paths:
        lowered = path.lower()
        for fragment in _FORBIDDEN_PATH_FRAGMENTS:
            if fragment in lowered:
                findings.append(path)
                break
    return findings


def is_bundle_size_within_limit(total_bytes: int, max_bytes: int) -> bool:
    return 0 <= total_bytes <= max_bytes


def bundle_checksum(inventory: list[dict[str, Any]]) -> str:
    return hashlib.sha256(dumps_json(inventory).encode("utf-8")).hexdigest()
