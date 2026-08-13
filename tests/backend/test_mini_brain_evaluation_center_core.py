"""MB-19: pure-module unit tests for core_model/mini_brain/evaluation_center/.

Covers deterministic benchmark outputs, regression comparison,
package-integrity failure detection, and honest-empty-input paths the
task spec's own testing section names.
"""

from core_model.mini_brain.evaluation_center.benchmark_export_builder import build_export_manifest
from core_model.mini_brain.evaluation_center.benchmark_registry import (
    BENCHMARK_CATEGORIES,
    build_benchmark_suite,
)
from core_model.mini_brain.evaluation_center.dataset_completeness_benchmark import (
    analyze_dataset_completeness,
)
from core_model.mini_brain.evaluation_center.evaluation_report_generator import generate_evaluation_report
from core_model.mini_brain.evaluation_center.grounding_benchmark import run_grounding_benchmark
from core_model.mini_brain.evaluation_center.language_benchmark import run_language_benchmark
from core_model.mini_brain.evaluation_center.multimodal_coverage_benchmark import (
    run_multimodal_coverage_benchmark,
)
from core_model.mini_brain.evaluation_center.ocr_benchmark import run_ocr_benchmark
from core_model.mini_brain.evaluation_center.package_integrity_benchmark import (
    run_package_integrity_benchmark,
)
from core_model.mini_brain.evaluation_center.regression_comparator import compare_against_baseline
from core_model.mini_brain.evaluation_center.release_readiness_evaluator import (
    BLOCKED,
    NEEDS_REVIEW,
    READY,
    evaluate_release_readiness,
)
from core_model.mini_brain.evaluation_center.retrieval_benchmark import run_retrieval_benchmark
from core_model.mini_brain.evaluation_center.score_aggregator import aggregate_scores

# -- benchmark_registry -------------------------------------------------------------------


def test_build_benchmark_suite_lists_fixed_categories() -> None:
    suite = build_benchmark_suite(
        topic="t", source_dataset_count=1, source_rag_session_count=1, source_training_package_count=1,
    )
    assert suite["categories"] == list(BENCHMARK_CATEGORIES)
    assert set(suite["metric_definitions"]) == set(BENCHMARK_CATEGORIES)
    assert suite["no_model_inference_required"] is True


# -- language_benchmark -------------------------------------------------------------------


def test_run_language_benchmark_empty_texts() -> None:
    report = run_language_benchmark(texts=[])
    assert report["records_analyzed"] == 0
    assert report["unicode_integrity"] is None
    assert "honestly empty" in report["disclosure"]


def test_run_language_benchmark_latin_text() -> None:
    report = run_language_benchmark(texts=["Hello world.", "A mountain scene with a river."])
    assert report["records_analyzed"] == 2
    assert report["unicode_integrity"] == 100.0
    assert report["dominant_language"] == "en"
    assert report["language_consistency"] == 100.0


def test_run_language_benchmark_mixed_language_lowers_consistency() -> None:
    report = run_language_benchmark(texts=["Hello world.", "இது ஒரு சோதனை வாக்கியம் ஆகும் இப்போது."])
    assert report["language_consistency"] < 100.0
    assert set(report["language_distribution"]) <= {"en", "ta", "mixed", "unknown", "tgl"}


# -- ocr_benchmark -------------------------------------------------------------------------


def test_run_ocr_benchmark_empty_groups() -> None:
    report = run_ocr_benchmark(evidence_groups=[])
    assert report["session_count"] == 0
    assert report["ocr_text_availability"] is None


def test_run_ocr_benchmark_matching_text_scores_no_conflict() -> None:
    report = run_ocr_benchmark(evidence_groups=[
        {"ocr_snippets": ["mountain river fish tree"], "text_snippets": ["mountain river fish tree"]},
    ])
    assert report["ocr_text_availability"] == 1.0
    assert report["ocr_conflict_ratio"] == 0.0
    assert report["ocr_dataset_overlap_ratio"] == 1.0


def test_run_ocr_benchmark_mismatched_text_flags_conflict() -> None:
    report = run_ocr_benchmark(evidence_groups=[
        {"ocr_snippets": ["mountain river fish tree scene"], "text_snippets": ["completely unrelated content here"]},
    ])
    assert report["ocr_conflict_ratio"] == 1.0


def test_run_ocr_benchmark_missing_ocr_excluded_from_evaluated_count() -> None:
    report = run_ocr_benchmark(evidence_groups=[{"ocr_snippets": [], "text_snippets": ["some text"]}])
    assert report["ocr_text_availability"] == 0.0
    assert report["evaluated_count"] == 0
    assert report["ocr_conflict_ratio"] == 0.0


# -- grounding_benchmark -------------------------------------------------------------------


def test_run_grounding_benchmark_no_sessions() -> None:
    report = run_grounding_benchmark(rag_sessions=[])
    assert report["session_count"] == 0
    assert "honestly unavailable" in report["disclosure"]


def test_run_grounding_benchmark_computes_averages() -> None:
    report = run_grounding_benchmark(rag_sessions=[
        {"answer": "the river is here [S1].", "citation_validity_rate": 1.0, "cited_evidence_count": 2, "total_evidence_count": 4},
        {"answer": "no citation here.", "citation_validity_rate": 0.5, "cited_evidence_count": 1, "total_evidence_count": 2},
    ])
    assert report["session_count"] == 2
    assert report["citation_validity_rate"] == 0.75
    assert report["evidence_coverage_rate"] == 0.5
    assert report["unsupported_sentence_ratio"] == 0.5


# -- retrieval_benchmark -------------------------------------------------------------------


def test_run_retrieval_benchmark_no_sessions() -> None:
    report = run_retrieval_benchmark(rag_sessions=[])
    assert report["session_count"] == 0


def test_run_retrieval_benchmark_computes_rates() -> None:
    report = run_retrieval_benchmark(rag_sessions=[
        {"evidence_count": 3, "average_relevance_score": 0.9, "answer_status": "grounded_answer"},
        {"evidence_count": 0, "average_relevance_score": None, "answer_status": "insufficient_evidence"},
    ])
    assert report["topk_evidence_availability"] == 0.5
    assert report["insufficient_evidence_rate"] == 0.5
    assert report["average_relevance_score"] == 0.9


# -- multimodal_coverage_benchmark ----------------------------------------------------------


def test_run_multimodal_coverage_benchmark_empty() -> None:
    report = run_multimodal_coverage_benchmark(record_type_counts={}, evidence_type_counts={})
    assert report["image_coverage"] is None
    assert "honestly empty" in report["disclosure"]


def test_run_multimodal_coverage_benchmark_computes_ratios() -> None:
    report = run_multimodal_coverage_benchmark(
        record_type_counts={"vision": 1, "qa": 1, "conversation": 2},
        evidence_type_counts={"object": 1, "graph_edge": 1, "text": 2},
    )
    assert report["image_coverage"] == 0.25
    assert report["qa_coverage"] == 0.25
    assert report["object_coverage"] == 0.25
    assert report["knowledge_graph_coverage"] == 0.25


def test_run_multimodal_coverage_benchmark_text_only_dataset_scores_zero_not_none() -> None:
    """A text-only dataset with real MB-16 records but no RAG evidence
    at all -- image/qa coverage still computed from records, but
    evidence-based metrics honestly score 0.0, never None."""
    report = run_multimodal_coverage_benchmark(
        record_type_counts={"conversation": 4}, evidence_type_counts={},
    )
    assert report["qa_coverage"] == 0.0
    assert report["object_coverage"] == 0.0
    assert report["knowledge_graph_coverage"] == 0.0


# -- dataset_completeness_benchmark ----------------------------------------------------------


def test_analyze_dataset_completeness_no_sessions() -> None:
    report = analyze_dataset_completeness(dataset_sessions=[])
    assert report["dataset_count"] == 0
    assert "honestly unavailable" in report["disclosure"]


def test_analyze_dataset_completeness_aggregates() -> None:
    report = analyze_dataset_completeness(dataset_sessions=[
        {"quality_report": {"overall_dataset_quality": 90.0}, "duplicate_report": {"exact_duplicate_count": 2}, "record_count": 10},
        {"quality_report": {"overall_dataset_quality": 80.0}, "duplicate_report": {"exact_duplicate_count": 0}, "record_count": 5},
    ])
    assert report["dataset_count"] == 2
    assert report["total_record_count"] == 15
    assert report["average_dataset_quality"] == 85.0
    assert report["total_exact_duplicate_count"] == 2


# -- package_integrity_benchmark --------------------------------------------------------------


def test_run_package_integrity_benchmark_no_packages() -> None:
    report = run_package_integrity_benchmark(package_checks=[])
    assert report["package_count"] == 0
    assert "honestly unavailable" in report["disclosure"]


def test_run_package_integrity_benchmark_all_valid() -> None:
    report = run_package_integrity_benchmark(package_checks=[
        {"session_public_id": "p1", "manifest_checksum_valid": True, "artifact_count_consistent": True, "missing_or_corrupt_file_count": 0},
    ])
    assert report["manifest_checksum_validity_rate"] == 1.0
    assert report["artifact_count_consistency_rate"] == 1.0
    assert report["missing_file_count"] == 0


def test_run_package_integrity_benchmark_detects_failure() -> None:
    """A checksum mismatch or missing file must be surfaced, never
    silently dropped -- this is the failure path release readiness
    depends on to block a bad package."""
    report = run_package_integrity_benchmark(package_checks=[
        {"session_public_id": "p1", "manifest_checksum_valid": False, "artifact_count_consistent": False, "missing_or_corrupt_file_count": 3},
    ])
    assert report["manifest_checksum_validity_rate"] == 0.0
    assert report["artifact_count_consistency_rate"] == 0.0
    assert report["missing_file_count"] == 3


# -- regression_comparator -----------------------------------------------------------------


def test_compare_against_baseline_no_baseline() -> None:
    report = compare_against_baseline(current_metrics={"a": 0.5}, baseline_metrics=None)
    assert report["has_baseline"] is False
    assert report["release_risk_level"] == "unknown"


def test_compare_against_baseline_detects_improvement_and_regression() -> None:
    report = compare_against_baseline(
        current_metrics={"a": 0.9, "b": 0.5}, baseline_metrics={"a": 0.7, "b": 0.8},
    )
    assert report["has_baseline"] is True
    assert [m["metric"] for m in report["improved_metrics"]] == ["a"]
    assert [m["metric"] for m in report["regressed_metrics"]] == ["b"]
    assert report["overall_drift_score"] == 0.3
    assert report["release_risk_level"] in {"medium", "high"}


def test_compare_against_baseline_identical_metrics_are_unchanged() -> None:
    report = compare_against_baseline(current_metrics={"a": 0.5}, baseline_metrics={"a": 0.5})
    assert report["unchanged_metrics"] == [{"metric": "a", "baseline": 0.5, "current": 0.5, "delta": 0.0}]
    assert report["release_risk_level"] == "low"


def test_compare_against_baseline_worse_than_baseline_is_high_risk() -> None:
    """A dataset that regressed on every single metric relative to the
    baseline must never be reported as low risk."""
    report = compare_against_baseline(
        current_metrics={"a": 0.3, "b": 0.2, "c": 0.1}, baseline_metrics={"a": 0.9, "b": 0.9, "c": 0.9},
    )
    assert len(report["regressed_metrics"]) == 3
    assert report["release_risk_level"] == "high"


def test_compare_against_baseline_missing_baseline_metric_not_scored() -> None:
    report = compare_against_baseline(current_metrics={"new_metric": 0.5}, baseline_metrics={"a": 0.5})
    assert report["missing_baseline_metrics"] == ["new_metric"]
    assert report["regressed_metrics"] == []
    assert report["improved_metrics"] == []


# -- score_aggregator ------------------------------------------------------------------------


def test_aggregate_scores_excludes_missing_categories() -> None:
    report = aggregate_scores(category_scores={"language": 90.0, "ocr": None, "grounding": 70.0})
    assert report["categories_scored"] == 2
    assert report["categories_total"] == 3
    assert report["overall_score"] == 80.0


def test_aggregate_scores_all_missing_is_none_not_zero() -> None:
    report = aggregate_scores(category_scores={"language": None, "ocr": None})
    assert report["overall_score"] is None


# -- release_readiness_evaluator --------------------------------------------------------------


def test_evaluate_release_readiness_ready_when_all_good() -> None:
    result = evaluate_release_readiness(
        overall_score=90.0, grounding_composite_score=80.0, package_integrity_ok=True,
        ocr_conflict_ratio=0.0, drift_score=0.0,
    )
    assert result["status"] == READY
    assert result["blocking_issues"] == []


def test_evaluate_release_readiness_blocked_on_grounding_quality() -> None:
    result = evaluate_release_readiness(
        overall_score=90.0, grounding_composite_score=30.0, package_integrity_ok=True,
        ocr_conflict_ratio=0.0, drift_score=0.0,
    )
    assert result["status"] == BLOCKED
    assert any("grounding quality" in issue for issue in result["blocking_issues"])


def test_evaluate_release_readiness_blocked_on_package_integrity_failure() -> None:
    result = evaluate_release_readiness(
        overall_score=90.0, grounding_composite_score=80.0, package_integrity_ok=False,
        ocr_conflict_ratio=0.0, drift_score=0.0,
    )
    assert result["status"] == BLOCKED
    assert any("package integrity" in issue for issue in result["blocking_issues"])


def test_evaluate_release_readiness_blocked_on_ocr_conflict_rate() -> None:
    result = evaluate_release_readiness(
        overall_score=90.0, grounding_composite_score=80.0, package_integrity_ok=True,
        ocr_conflict_ratio=0.5, drift_score=0.0,
    )
    assert result["status"] == BLOCKED
    assert any("OCR conflict" in issue for issue in result["blocking_issues"])


def test_evaluate_release_readiness_blocked_on_severe_drift() -> None:
    result = evaluate_release_readiness(
        overall_score=90.0, grounding_composite_score=80.0, package_integrity_ok=True,
        ocr_conflict_ratio=0.0, drift_score=0.5,
    )
    assert result["status"] == BLOCKED
    assert any("regression drift" in issue for issue in result["blocking_issues"])


def test_evaluate_release_readiness_needs_review_for_middling_score() -> None:
    result = evaluate_release_readiness(
        overall_score=55.0, grounding_composite_score=80.0, package_integrity_ok=True,
        ocr_conflict_ratio=0.0, drift_score=0.0,
    )
    assert result["status"] == NEEDS_REVIEW


def test_evaluate_release_readiness_thresholds_documented() -> None:
    result = evaluate_release_readiness(
        overall_score=90.0, grounding_composite_score=80.0, package_integrity_ok=True,
        ocr_conflict_ratio=0.0, drift_score=0.0,
    )
    assert set(result["thresholds"]) == {
        "grounding_quality_threshold", "ocr_conflict_threshold", "severe_drift_threshold",
        "ready_overall_score_threshold", "needs_review_overall_score_threshold",
    }


# -- evaluation_report_generator ---------------------------------------------------------------


def _report_kwargs(**overrides):
    base = dict(
        session_public_id="e1", topic="t",
        dataset_collection_report={"accepted_count": 1}, rag_collection_report={"accepted_count": 1},
        package_collection_report={"accepted_count": 1},
        language_benchmark_report={"unicode_integrity": 100.0}, ocr_benchmark_report={"ocr_text_availability": 1.0},
        grounding_benchmark_report={"citation_validity_rate": 1.0}, retrieval_benchmark_report={"topk_evidence_availability": 1.0},
        multimodal_benchmark_report={"image_coverage": 0.5}, package_benchmark_report={"missing_file_count": 0},
        regression_report={"has_baseline": False}, score_summary={"overall_score": 90.0, "category_scores": {}},
        release_readiness={"status": "Ready", "blocking_issues": []},
    )
    base.update(overrides)
    return base


def test_generate_evaluation_report_discloses_all_honest_limitations() -> None:
    report = generate_evaluation_report(**_report_kwargs())
    assert report["no_model_inference_performed"] is True
    assert report["no_benchmark_against_real_model_outputs"] is True
    assert report["no_semantic_correctness_verification_performed"] is True
    assert report["retrieval_quality_limited_to_stored_evidence"] is True
    assert report["release_readiness_is_metadata_based"] is True
    assert report["evaluation_approval_does_not_guarantee_production_model_quality"] is True
    assert "never guarantee" in report["disclaimer"] or "does not guarantee" in report["disclaimer"]


def test_generate_evaluation_report_status_matches_readiness() -> None:
    report = generate_evaluation_report(**_report_kwargs(release_readiness={"status": "Blocked", "blocking_issues": ["x"]}))
    assert report["status"] == "Blocked"
    assert report["blocking_issues"] == ["x"]


# -- benchmark_export_builder --------------------------------------------------------------------


def test_build_export_manifest_excludes_self_and_discloses() -> None:
    entries = [{"artifact_name": "benchmark_summary.json", "relative_path": "benchmark_summary.json", "sha256": "x", "file_size_bytes": 1}]
    manifest = build_export_manifest(
        session_public_id="e1", topic="t", overall_score=90.0, release_readiness_status="Ready",
        artifact_entries=entries, created_at="2026-01-01",
    )
    assert manifest["artifact_count"] == 1
    assert manifest["training_performed"] is False
    assert manifest["model_inference_performed"] is False
    assert "not self-listed" in manifest["note"]
    assert manifest["sensitive_content_warnings"] == []
