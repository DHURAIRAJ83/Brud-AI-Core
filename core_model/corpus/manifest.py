"""Corpus manifest checksum and sensitive-content scanning.

Reuses Phase 14's checksum/scan implementation unchanged (via Phase
16/17/18's own re-export) -- no fifth implementation of the same
tamper-detection and secret/path-scanning logic in this project.
"""

from __future__ import annotations

from typing import Any

from core_model.rag.manifest import (
    manifest_checksum,
    scan_for_sensitive_content,
    verify_manifest_checksum,
)

__all__ = [
    "manifest_checksum",
    "scan_for_sensitive_content",
    "verify_manifest_checksum",
    "REQUIRED_CORPUS_MANIFEST_FIELDS",
    "missing_required_fields",
]

REQUIRED_CORPUS_MANIFEST_FIELDS = (
    "corpus_policy_checksum",
    "source_registry_public_ids",
    "source_licence_decisions",
    "source_snapshot_checksums",
    "extraction_configuration",
    "normalization_configuration",
    "ocr_cleanup_configuration",
    "segmentation_configuration",
    "privacy_detector_version",
    "safety_detector_version",
    "quality_thresholds",
    "deduplication_configuration",
    "contamination_configuration",
    "collection_checksums",
    "balance_policy_checksum",
    "partition_configuration",
    "segment_counts",
    "language_distribution",
    "domain_distribution",
    "style_distribution",
    "licence_distribution",
    "excluded_item_counts",
    "corpus_version",
    "export_shard_checksums",
    "known_limitations",
    "software_versions",
    "created_at",
)


def missing_required_fields(manifest: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_CORPUS_MANIFEST_FIELDS if field not in manifest]
