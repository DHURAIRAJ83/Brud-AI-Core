"""Deterministic quality assessment for semantic chunks (Phase 5, Step 20).

Mirrors the shape of `core_model.manual_data.quality`: per-dimension
0-100 scores plus severity-independent *blocking issue* codes that
force the recommended status regardless of how high the average score
is -- a chunk with one blocking issue is never recommended for
approval just because its other dimensions score well.
"""

from __future__ import annotations

from typing import Any, TypedDict

DIMENSIONS = (
    "boundary_completeness",
    "semantic_coherence",
    "language_correctness",
    "source_traceability",
    "structure_completeness",
    "content_integrity",
    "format_validity",
    "uniqueness",
)

DEFAULT_APPROVAL_THRESHOLD = 85


class ChunkQualityResult(TypedDict):
    dimension_scores: dict[str, float]
    overall_score: float
    blocking_issues: list[str]
    warnings: list[str]
    recommended_status: str


def assess_chunk_quality(
    *,
    chunk: dict[str, Any],
    revision: dict[str, Any],
    page_approved: bool,
    coverage_issue_codes: list[str] | None = None,
    relations_valid: bool = True,
    duplicate_status: str = "unique",
    usage_decision: dict[str, Any] | None = None,
    approval_threshold: int = DEFAULT_APPROVAL_THRESHOLD,
) -> ChunkQualityResult:
    coverage_issue_codes = coverage_issue_codes or []
    text = (revision.get("text") or "").strip()
    chunk_type = chunk.get("chunk_type", "unknown")

    blocking_issues: list[str] = []
    warnings: list[str] = []

    has_lineage = bool(revision.get("document_page_id") and revision.get("page_number"))
    if not has_lineage:
        blocking_issues.append("MISSING_SOURCE_LINEAGE")
    if not page_approved:
        blocking_issues.append("UNAPPROVED_PAGE_SOURCE")
    if not text:
        blocking_issues.append("EMPTY_CHUNK")
    if text and text[-1:] not in ".!?।॥\"'”)":
        # A chunk that doesn't end on sentence-like punctuation is only a
        # *warning* for most types (many legitimate fragments -- headings,
        # table cells, list items -- never end in punctuation), but is a
        # blocking issue specifically for prose types where a broken
        # sentence boundary would silently corrupt training data.
        if chunk_type in ("paragraph", "definition", "example"):
            blocking_issues.append("BROKEN_SENTENCE_BOUNDARY")
        else:
            warnings.append("no_terminal_punctuation")
    if "SOURCE_TEXT_LOSS" in coverage_issue_codes:
        blocking_issues.append("SOURCE_TEXT_LOSS")
    if "SOURCE_TEXT_OVERLAP" in coverage_issue_codes:
        blocking_issues.append("SOURCE_TEXT_OVERLAP")
    if not relations_valid:
        blocking_issues.append("INVALID_RELATION")
    if chunk_type == "table" and (revision.get("metadata") or {}).get("table_structure") == "raw":
        blocking_issues.append("UNRESOLVED_TABLE_STRUCTURE")
    if revision.get("origin") == "human_synthesized" and not revision.get("reviewed"):
        blocking_issues.append("UNREVIEWED_ADMIN_SYNTHESIS")
    if usage_decision is not None and not usage_decision.get("allowed"):
        blocking_issues.append("RIGHTS_BLOCK_TARGET_USE")

    dimension_scores: dict[str, float] = {
        "boundary_completeness": 100.0 if not coverage_issue_codes else 20.0,
        "semantic_coherence": 90.0 if len(text) >= 20 else 40.0,
        "language_correctness": 80.0 if chunk.get("language", "unknown") != "unknown" else 55.0,
        "source_traceability": 100.0 if has_lineage else 0.0,
        "structure_completeness": 100.0 if chunk_type != "unknown" else 40.0,
        "content_integrity": 100.0 if text else 0.0,
        "format_validity": 100.0
        if chunk_type != "table" or revision.get("metadata", {}).get("table_structure") != "raw"
        else 50.0,
        "uniqueness": {"unique": 100.0, "possible_duplicate": 50.0}.get(duplicate_status, 0.0),
    }
    overall_score = round(sum(dimension_scores.values()) / len(dimension_scores), 2)

    if duplicate_status == "exact_duplicate":
        warnings.append("exact_duplicate_chunk_detected")
    elif duplicate_status == "possible_duplicate":
        warnings.append("possible_duplicate_chunk_detected")

    if blocking_issues:
        recommended_status = "needs_review"
        if "EMPTY_CHUNK" in blocking_issues or "MISSING_SOURCE_LINEAGE" in blocking_issues:
            recommended_status = "draft"
        elif "SOURCE_TEXT_LOSS" in blocking_issues or "SOURCE_TEXT_OVERLAP" in blocking_issues:
            recommended_status = "needs_structure_review"
        elif "UNREVIEWED_ADMIN_SYNTHESIS" in blocking_issues:
            recommended_status = "needs_content_review"
    elif overall_score >= approval_threshold:
        recommended_status = "approved"
    else:
        recommended_status = "needs_review"

    return {
        "dimension_scores": dimension_scores,
        "overall_score": overall_score,
        "blocking_issues": blocking_issues,
        "warnings": warnings,
        "recommended_status": recommended_status,
    }
