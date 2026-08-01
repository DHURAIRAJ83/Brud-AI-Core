"""Normalizes the three existing, structurally different quality
results (`backend.services.dataset_quality`'s 7-dimension + severity
list; `core_model.manual_data.quality`'s 8-dimension + blocking_issues
list; `core_model.semantic_chunk.quality`'s identical 8-dimension shape)
into one canonical shape for the governance layer (Step 7).

This is a *mapping* layer, never a recomputation: `overall_score` is
always the subsystem's own reported score, verbatim, never re-averaged
from a subset of canonical buckets -- a subsystem's quality result
remains the single source of truth, and this adapter only relabels it
for consistent display/gating. A canonical bucket the source system
does not measure is left as `None` (never fabricated as a number),
and the full original dimension dict is preserved in
`metadata.source_dimensions` for audit (see plan doc section 6, risk 3).
"""

from __future__ import annotations

from typing import Any, TypedDict

from core_model.data_governance.issue_taxonomy import categorize_issue_code

CANONICAL_DIMENSIONS = (
    "language",
    "meaning",
    "factual",
    "source",
    "structure",
    "integrity",
    "format",
    "uniqueness",
)


class NormalizedQuality(TypedDict):
    overall_score: float
    dimension_scores: dict[str, float | None]
    is_blocked: bool
    blocking_issue_codes: list[str]
    issue_categories: list[dict[str, str]]
    warnings: list[str]
    metadata: dict[str, Any]


def _bucket_scores(
    source_dimensions: dict[str, float], bucket_map: dict[str, list[str]]
) -> dict[str, float | None]:
    scores: dict[str, float | None] = {}
    for bucket in CANONICAL_DIMENSIONS:
        source_dims = bucket_map.get(bucket, [])
        values = [source_dimensions[name] for name in source_dims if name in source_dimensions]
        scores[bucket] = round(sum(values) / len(values), 4) if values else None
    return scores


_DATASET_QUALITY_BUCKET_MAP: dict[str, list[str]] = {
    "language": ["language"],
    "meaning": ["text_quality"],
    "factual": [],
    "source": ["provenance"],
    "structure": ["structure"],
    "integrity": ["completeness", "safety"],
    "format": [],
    "uniqueness": ["duplication"],
}

_MANUAL_DATA_BUCKET_MAP: dict[str, list[str]] = {
    "language": ["language_correctness"],
    "meaning": ["meaning_correctness", "naturalness"],
    "factual": ["factual_confidence"],
    "source": ["source_reliability"],
    "structure": ["completeness"],
    "integrity": [],
    "format": ["format_validity"],
    "uniqueness": ["uniqueness"],
}

_SEMANTIC_CHUNK_BUCKET_MAP: dict[str, list[str]] = {
    "language": ["language_correctness"],
    "meaning": ["semantic_coherence"],
    "factual": [],
    "source": ["source_traceability"],
    "structure": ["structure_completeness", "boundary_completeness"],
    "integrity": ["content_integrity"],
    "format": ["format_validity"],
    "uniqueness": ["uniqueness"],
}


def normalize_dataset_quality_result(assessment: dict[str, Any]) -> NormalizedQuality:
    """`assessment` is the shape returned by `DatasetQualityService.latest()`
    / `.assess_record()`: `{scores: {...,overall}, readiness_status,
    issues: [{issue_code, severity, ...}]}`."""

    scores = dict(assessment.get("scores") or {})
    overall = scores.pop("overall", 0.0)
    issues = assessment.get("issues") or []
    blocking_codes = sorted(
        {issue["issue_code"] for issue in issues if issue.get("severity") == "blocking"}
    )
    is_blocked = bool(blocking_codes) or assessment.get("readiness_status") == "blocked"
    issue_categories = [
        {"issue_code": code, "issue_category": categorize_issue_code("dataset_quality", code)}
        for code in blocking_codes
    ]
    return {
        "overall_score": overall,
        "dimension_scores": _bucket_scores(scores, _DATASET_QUALITY_BUCKET_MAP),
        "is_blocked": is_blocked,
        "blocking_issue_codes": blocking_codes,
        "issue_categories": issue_categories,
        "warnings": sorted(
            {issue["issue_code"] for issue in issues if issue.get("severity") == "warning"}
        ),
        "metadata": {
            "source_system": "dataset_quality",
            "source_dimensions": scores,
            "source_overall": overall,
            "source_readiness_status": assessment.get("readiness_status", "not_assessed"),
        },
    }


def normalize_manual_data_quality_result(result: dict[str, Any]) -> NormalizedQuality:
    """`result` is the shape returned by
    `core_model.manual_data.quality.assess_quality()`."""

    dimension_scores = dict(result.get("dimension_scores") or {})
    blocking = list(result.get("blocking_issues") or [])
    issue_categories = [
        {"issue_code": code, "issue_category": categorize_issue_code("manual_data", code)}
        for code in blocking
    ]
    return {
        "overall_score": result.get("overall_score", 0.0),
        "dimension_scores": _bucket_scores(dimension_scores, _MANUAL_DATA_BUCKET_MAP),
        "is_blocked": bool(blocking),
        "blocking_issue_codes": blocking,
        "issue_categories": issue_categories,
        "warnings": list(result.get("warnings") or []),
        "metadata": {
            "source_system": "manual_data",
            "source_dimensions": dimension_scores,
            "source_overall": result.get("overall_score", 0.0),
            "source_recommended_status": result.get("recommended_status", "draft"),
        },
    }


def normalize_chunk_quality_result(result: dict[str, Any]) -> NormalizedQuality:
    """`result` is the shape returned by
    `core_model.semantic_chunk.quality.assess_chunk_quality()`."""

    dimension_scores = dict(result.get("dimension_scores") or {})
    blocking = list(result.get("blocking_issues") or [])
    issue_categories = [
        {"issue_code": code, "issue_category": categorize_issue_code("semantic_chunk", code)}
        for code in blocking
    ]
    return {
        "overall_score": result.get("overall_score", 0.0),
        "dimension_scores": _bucket_scores(dimension_scores, _SEMANTIC_CHUNK_BUCKET_MAP),
        "is_blocked": bool(blocking),
        "blocking_issue_codes": blocking,
        "issue_categories": issue_categories,
        "warnings": list(result.get("warnings") or []),
        "metadata": {
            "source_system": "semantic_chunk",
            "source_dimensions": dimension_scores,
            "source_overall": result.get("overall_score", 0.0),
            "source_recommended_status": result.get("recommended_status", "draft"),
        },
    }


__all__ = [
    "CANONICAL_DIMENSIONS",
    "NormalizedQuality",
    "normalize_dataset_quality_result",
    "normalize_manual_data_quality_result",
    "normalize_chunk_quality_result",
]
