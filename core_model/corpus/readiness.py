"""Phase 20 formal pretraining-readiness gate -- pure aggregation only.

Every dimension is scored independently (never one combined score),
and warnings are never silently upgraded to pass: the final result is
``ready`` only when every dimension actually passed.
"""

from __future__ import annotations

from typing import Any

READINESS_DIMENSIONS = (
    "source_governance",
    "licence_compliance",
    "provenance_completeness",
    "privacy_safety",
    "content_safety",
    "extraction_quality",
    "normalization_integrity",
    "segment_quality",
    "deduplication_completion",
    "contamination_completion",
    "balance_adequacy",
    "partition_integrity",
    "tokenizer_compatibility",
    "manifest_integrity",
    "export_integrity",
)

DIMENSION_STATUSES = ("pass", "warning", "fail", "not_evaluated")
READINESS_RESULTS = ("not_ready", "ready_with_warnings", "ready")


def overall_readiness(dimension_results: dict[str, str]) -> str:
    """Never silently converts a warning to a pass, and never claims
    full readiness while a dimension remains unevaluated."""

    if any(status == "fail" for status in dimension_results.values()):
        return "not_ready"
    if any(status in ("warning", "not_evaluated") for status in dimension_results.values()):
        return "ready_with_warnings"
    return "ready"


def build_readiness_report(dimension_results: dict[str, str]) -> dict[str, Any]:
    return {
        "overall_result": overall_readiness(dimension_results),
        "dimensions": dict(dimension_results),
        "pass_count": sum(1 for s in dimension_results.values() if s == "pass"),
        "warning_count": sum(1 for s in dimension_results.values() if s == "warning"),
        "fail_count": sum(1 for s in dimension_results.values() if s == "fail"),
        "not_evaluated_count": sum(1 for s in dimension_results.values() if s == "not_evaluated"),
    }
