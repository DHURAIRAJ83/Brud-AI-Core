"""Governance-aware manifest extension (Step 9).

Pure assembly of already-computed summaries into the additive manifest
dict keys -- never touches the existing manifest's own fields or its
`_checksum_payload()` (see plan doc section 1.1): this phase's checksum
covers only the new keys, computed separately, so no pre-Phase-7
version's `verify_version()` is ever affected.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def build_manifest_extension(
    *,
    build_request_code: str,
    target_pipeline: str,
    dataset_version_public_id: str,
    record_type_counts: dict[str, int],
    language_counts: dict[str, int],
    domain_counts: dict[str, int],
    source_counts: dict[str, int],
    rights_status_counts: dict[str, int],
    verification_status_counts: dict[str, int],
    quality_summary: dict[str, Any],
    duplicate_resolution_summary: dict[str, Any],
    conflict_resolution_summary: dict[str, Any],
    approval_summary: dict[str, Any],
    legacy_record_count: int,
    override_count: int,
    attribution_entries: list[dict[str, Any]],
    created_at: str,
) -> dict[str, Any]:
    record_count = sum(record_type_counts.values())
    extension: dict[str, Any] = {
        "build_request_code": build_request_code,
        "target_pipeline": target_pipeline,
        "dataset_version_id": dataset_version_public_id,
        "record_count": record_count,
        "record_type_counts": dict(record_type_counts),
        "language_counts": dict(language_counts),
        "domain_counts": dict(domain_counts),
        "source_counts": dict(source_counts),
        "rights_status_counts": dict(rights_status_counts),
        "verification_status_counts": dict(verification_status_counts),
        "quality_summary": dict(quality_summary),
        "duplicate_resolution_summary": dict(duplicate_resolution_summary),
        "conflict_resolution_summary": dict(conflict_resolution_summary),
        "approval_summary": dict(approval_summary),
        "legacy_record_count": legacy_record_count,
        "override_count": override_count,
        "attribution_entries": list(attribution_entries),
        "created_at": created_at,
    }
    extension["source_manifest_checksum"] = _checksum({
        "source_counts": extension["source_counts"],
        "rights_status_counts": extension["rights_status_counts"],
        "attribution_entries": extension["attribution_entries"],
    })
    extension["record_manifest_checksum"] = _checksum({
        "record_type_counts": extension["record_type_counts"],
        "language_counts": extension["language_counts"],
        "record_count": extension["record_count"],
    })
    return extension


def _checksum(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["build_manifest_extension"]
