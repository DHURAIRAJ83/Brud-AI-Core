from __future__ import annotations

from core_model.data_governance.quality_adapter import (
    normalize_chunk_quality_result,
    normalize_dataset_quality_result,
    normalize_manual_data_quality_result,
)


def test_normalize_dataset_quality_never_recomputes_overall_score():
    assessment = {
        "scores": {
            "completeness": 1.0,
            "structure": 1.0,
            "language": 1.0,
            "text_quality": 1.0,
            "duplication": 1.0,
            "safety": 1.0,
            "provenance": 1.0,
            "overall": 0.5,
        },
        "readiness_status": "warning",
        "issues": [{"issue_code": "unknown_language", "severity": "warning"}],
    }
    result = normalize_dataset_quality_result(assessment)
    assert result["overall_score"] == 0.5
    assert result["is_blocked"] is False
    assert result["dimension_scores"]["language"] == 1.0
    assert result["dimension_scores"]["factual"] is None
    assert "overall" not in result["metadata"]["source_dimensions"]
    assert result["metadata"]["source_system"] == "dataset_quality"


def test_normalize_dataset_quality_marks_blocked_on_blocking_severity():
    assessment = {
        "scores": {
            "completeness": 0.2,
            "structure": 0.3,
            "language": 1.0,
            "text_quality": 1.0,
            "duplication": 1.0,
            "safety": 1.0,
            "provenance": 1.0,
            "overall": 0.7,
        },
        "readiness_status": "ready",
        "issues": [{"issue_code": "missing_required_field", "severity": "blocking"}],
    }
    result = normalize_dataset_quality_result(assessment)
    assert result["is_blocked"] is True
    assert result["blocking_issue_codes"] == ["missing_required_field"]
    assert result["issue_categories"] == [
        {"issue_code": "missing_required_field", "issue_category": "format_invalid"}
    ]


def test_normalize_manual_data_quality_preserves_overall_and_blocking():
    result = normalize_manual_data_quality_result(
        {
            "dimension_scores": {
                "language_correctness": 90.0,
                "meaning_correctness": 80.0,
                "naturalness": 85.0,
                "completeness": 100.0,
                "source_reliability": 40.0,
                "factual_confidence": 15.0,
                "format_validity": 100.0,
                "uniqueness": 100.0,
            },
            "overall_score": 76.25,
            "blocking_issues": ["HIGH_RISK_UNVERIFIED"],
            "warnings": [],
            "recommended_status": "needs_source_verification",
        }
    )
    assert result["overall_score"] == 76.25
    assert result["is_blocked"] is True
    assert result["blocking_issue_codes"] == ["HIGH_RISK_UNVERIFIED"]
    assert result["issue_categories"] == [
        {"issue_code": "HIGH_RISK_UNVERIFIED", "issue_category": "high_risk_unverified"}
    ]
    assert result["dimension_scores"]["factual"] == 15.0
    assert result["dimension_scores"]["integrity"] is None


def test_normalize_chunk_quality_maps_boundary_and_structure_completeness():
    result = normalize_chunk_quality_result(
        {
            "dimension_scores": {
                "boundary_completeness": 100.0,
                "semantic_coherence": 90.0,
                "language_correctness": 80.0,
                "source_traceability": 100.0,
                "structure_completeness": 100.0,
                "content_integrity": 100.0,
                "format_validity": 100.0,
                "uniqueness": 100.0,
            },
            "overall_score": 96.25,
            "blocking_issues": [],
            "warnings": [],
            "recommended_status": "approved",
        }
    )
    assert result["is_blocked"] is False
    assert result["overall_score"] == 96.25
    assert result["dimension_scores"]["structure"] == 100.0
    assert result["metadata"]["source_system"] == "semantic_chunk"


def test_unmeasured_canonical_buckets_are_never_fabricated():
    result = normalize_dataset_quality_result(
        {
            "scores": {"language": 1.0, "overall": 1.0},
            "readiness_status": "ready",
            "issues": [],
        }
    )
    for bucket in ("factual", "format"):
        assert result["dimension_scores"][bucket] is None
