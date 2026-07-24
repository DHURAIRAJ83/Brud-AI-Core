"""RAG manifest checksum and sensitive-content scanning.

Reuses Phase 14's checksum/scan implementation unchanged
(``core_model.release.manifest``) — no second implementation of the
same tamper-detection and secret/path-scanning logic.
"""

from __future__ import annotations

from typing import Any

from core_model.release.manifest import (
    manifest_checksum,
    scan_for_sensitive_content,
    verify_manifest_checksum,
)

__all__ = [
    "manifest_checksum",
    "scan_for_sensitive_content",
    "verify_manifest_checksum",
    "REQUIRED_RAG_MANIFEST_FIELDS",
    "missing_required_fields",
]

REQUIRED_RAG_MANIFEST_FIELDS = (
    "knowledge_space_public_id",
    "source_versions",
    "chunk_set_checksum",
    "chunking_configuration",
    "embedding_model",
    "embedding_run_checksum",
    "vector_index_checksum",
    "keyword_index_checksum",
    "retrieval_profile_checksum",
    "inference_assignment_version",
    "model_release_checksums",
    "context_policy",
    "injection_filter_configuration",
    "known_limitations",
    "software_versions",
    "created_at",
)


def missing_required_fields(manifest: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_RAG_MANIFEST_FIELDS if field not in manifest]
