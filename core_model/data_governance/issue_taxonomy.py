"""Maps every issue code the *existing* quality/verification subsystems
already produce onto Phase 6's 20 stable `issue_category` values (Step
5). This is a lookup table, not a new detector: every code below is
produced today by `backend.services.dataset_quality`,
`core_model.manual_data.quality`, or `core_model.semantic_chunk.quality`
-- see docs/data_studio/phase6_quality_duplicate_conflict_approval_plan.md
section 5.

Deliberately raises on an unrecognized code rather than guessing a
category: silently mis-filing an issue this phase has never seen would
violate the "never fabricate quality/duplicate/verification/approval
data" rule just as much as inventing one from nothing would.
"""

from __future__ import annotations

from core_model.data_governance.review import ISSUE_CATEGORIES

# backend.services.dataset_quality issue_code -> issue_category
DATASET_QUALITY_ISSUE_CATEGORIES: dict[str, str] = {
    "missing_required_field": "format_invalid",
    "empty_or_whitespace_only": "format_invalid",
    "text_too_long": "format_invalid",
    "text_too_short": "format_invalid",
    "unknown_language": "language_quality",
    "language_script_mismatch": "language_quality",
    "replacement_character": "language_quality",
    "low_letter_ratio": "language_quality",
    "excessive_punctuation": "language_quality",
    "excessive_repetition": "language_quality",
    "suspicious_unicode": "format_invalid",
    "duplicate_existing": "exact_duplicate",
    "unsafe_metadata": "format_invalid",
    "missing_source_provenance": "source_traceability",
    "rejected_licence": "rights_restriction",
    "unknown_licence": "rights_restriction",
}

# core_model.manual_data.quality blocking_issues code -> issue_category
MANUAL_DATA_ISSUE_CATEGORIES: dict[str, str] = {
    "MISSING_SOURCE": "source_traceability",
    "EMPTY_REQUIRED_FIELD": "format_invalid",
    "HIGH_RISK_UNVERIFIED": "high_risk_unverified",
    "AI_ASSISTED_UNREVIEWED": "ai_assisted_unreviewed",
    "INVALID_LANGUAGE_PAIR": "format_invalid",
    "TRANSLATION_UNVERIFIED": "translation_conflict",
    "FACTUAL_CONFLICT": "factual_accuracy",
    "RIGHTS_BLOCK_TRAINING": "rights_restriction",
}

# core_model.semantic_chunk.quality blocking_issues code -> issue_category
SEMANTIC_CHUNK_ISSUE_CATEGORIES: dict[str, str] = {
    "MISSING_SOURCE_LINEAGE": "source_traceability",
    "UNAPPROVED_PAGE_SOURCE": "source_traceability",
    "EMPTY_CHUNK": "format_invalid",
    "BROKEN_SENTENCE_BOUNDARY": "language_quality",
    "SOURCE_TEXT_LOSS": "chunk_gap",
    "SOURCE_TEXT_OVERLAP": "chunk_overlap",
    "INVALID_RELATION": "revision_conflict",
    "UNRESOLVED_TABLE_STRUCTURE": "format_invalid",
    "UNREVIEWED_ADMIN_SYNTHESIS": "ai_assisted_unreviewed",
    "RIGHTS_BLOCK_TARGET_USE": "rights_restriction",
}

_SOURCE_SYSTEM_MAPS: dict[str, dict[str, str]] = {
    "dataset_quality": DATASET_QUALITY_ISSUE_CATEGORIES,
    "manual_data": MANUAL_DATA_ISSUE_CATEGORIES,
    "semantic_chunk": SEMANTIC_CHUNK_ISSUE_CATEGORIES,
}


def categorize_issue_code(source_system: str, issue_code: str) -> str:
    """Look up the governance `issue_category` for a code a subsystem
    already produced. Raises `ValueError` for an unmapped
    (source_system, issue_code) pair rather than defaulting silently."""

    mapping = _SOURCE_SYSTEM_MAPS.get(source_system)
    if mapping is None:
        raise ValueError(f"unknown source_system: {source_system}")
    category = mapping.get(issue_code)
    if category is None:
        raise ValueError(f"unmapped issue_code {issue_code!r} from source_system {source_system!r}")
    assert category in ISSUE_CATEGORIES
    return category


__all__ = [
    "DATASET_QUALITY_ISSUE_CATEGORIES",
    "MANUAL_DATA_ISSUE_CATEGORIES",
    "SEMANTIC_CHUNK_ISSUE_CATEGORIES",
    "categorize_issue_code",
]
