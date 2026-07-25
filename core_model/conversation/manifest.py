"""Conversation-memory manifest checksum and sensitive-content scanning.

Reuses Phase 14's checksum/scan implementation unchanged (via Phase 16's
own re-export), so there is no third implementation of the same
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
    "REQUIRED_CONVERSATION_MEMORY_MANIFEST_FIELDS",
    "missing_required_fields",
]

REQUIRED_CONVERSATION_MEMORY_MANIFEST_FIELDS = (
    "memory_policy_public_id",
    "memory_policy_checksum",
    "session_mode_configuration",
    "summary_policy",
    "consent_policy",
    "allowed_memory_categories",
    "forbidden_memory_categories",
    "memory_retrieval_profile",
    "embedding_index_lineage",
    "rag_profile_lineage",
    "inference_assignment_version",
    "context_budget_configuration",
    "evaluation_suite_checksum",
    "retrieval_metrics",
    "privacy_isolation_metrics",
    "known_limitations",
    "software_versions",
    "created_at",
)


def missing_required_fields(manifest: dict[str, Any]) -> list[str]:
    return [
        field for field in REQUIRED_CONVERSATION_MEMORY_MANIFEST_FIELDS if field not in manifest
    ]
