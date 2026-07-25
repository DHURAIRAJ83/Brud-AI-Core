"""Feedback manifest checksum and sensitive-content scanning.

Reuses Phase 14's checksum/scan implementation unchanged (via Phase
16/17's own re-export), so there is no fourth implementation of the
same tamper-detection and secret/path-scanning logic in this project.
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
    "REQUIRED_FEEDBACK_MANIFEST_FIELDS",
    "missing_required_fields",
]

REQUIRED_FEEDBACK_MANIFEST_FIELDS = (
    "feedback_policy_public_id",
    "feedback_policy_checksum",
    "feedback_counts_by_type",
    "feedback_counts_by_classification",
    "privacy_finding_summary",
    "safety_finding_summary",
    "review_rubric_version",
    "candidate_checksums",
    "deduplication_configuration",
    "contamination_configuration",
    "regression_suite_checksum",
    "model_comparison_results",
    "improvement_report_checksum",
    "known_limitations",
    "software_versions",
    "created_at",
)


def missing_required_fields(manifest: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_FEEDBACK_MANIFEST_FIELDS if field not in manifest]
