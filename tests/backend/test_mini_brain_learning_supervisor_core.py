"""MB-06: pure-module unit tests for
core_model/mini_brain/learning_supervisor/."""

from core_model.mini_brain.learning_supervisor.learning_report_generator import (
    generate_learning_report,
)
from core_model.mini_brain.learning_supervisor.model_comparator import compare_models
from core_model.mini_brain.learning_supervisor.recommendation_engine import (
    generate_learning_recommendations,
)
from core_model.mini_brain.learning_supervisor.training_request_builder import (
    HYPERPARAMETER_PROFILES,
    available_profiles,
    build_training_request,
)
from core_model.mini_brain.learning_supervisor.training_request_validator import (
    validate_training_request,
)
from core_model.mini_brain.learning_supervisor.training_result_analyzer import (
    analyze_training_result,
)

# -- training_request_validator -----------------------------------------------


def _ready(status="Ready", reasons=None):
    return {"status": status, "reasons": reasons or [], "clean_ratio": 0.9, "duplicate_ratio": 0.01}


def test_validator_blocks_when_dataset_not_approved() -> None:
    result = validate_training_request(
        dataset_readiness=_ready(), dataset_decision=None, rag_required=True,
        rag_decision="approve", advanced_risk=None, advanced_conflicts=None,
    )
    assert not result["valid"]
    assert any("dataset readiness" in b for b in result["blockers"])


def test_validator_blocks_when_rag_required_but_not_approved() -> None:
    result = validate_training_request(
        dataset_readiness=_ready(), dataset_decision="approve", rag_required=True,
        rag_decision=None, advanced_risk=None, advanced_conflicts=None,
    )
    assert not result["valid"]
    assert any("RAG evaluation" in b for b in result["blockers"])


def test_validator_blocks_on_not_ready_dataset_status() -> None:
    result = validate_training_request(
        dataset_readiness=_ready(status="Not Ready", reasons=["too few records"]),
        dataset_decision="approve", rag_required=False, rag_decision=None,
        advanced_risk=None, advanced_conflicts=None,
    )
    assert not result["valid"]
    assert any("Not Ready" in b for b in result["blockers"])


def test_validator_warns_but_passes_on_needs_improvement() -> None:
    result = validate_training_request(
        dataset_readiness=_ready(status="Needs Improvement", reasons=["clean_ratio low"]),
        dataset_decision="approve", rag_required=False, rag_decision=None,
        advanced_risk=None, advanced_conflicts=None,
    )
    assert result["valid"]
    assert result["warnings"]


def test_validator_blocks_on_critical_risk_item() -> None:
    result = validate_training_request(
        dataset_readiness=_ready(), dataset_decision="approve", rag_required=False, rag_decision=None,
        advanced_risk={"risk_items": [{"severity": "critical"}], "risk_item_count": 1},
        advanced_conflicts=None,
    )
    assert not result["valid"]
    assert any("critical" in b for b in result["blockers"])


def test_validator_warns_on_non_critical_risk_item() -> None:
    result = validate_training_request(
        dataset_readiness=_ready(), dataset_decision="approve", rag_required=False, rag_decision=None,
        advanced_risk={"risk_items": [{"severity": "medium"}], "risk_item_count": 1},
        advanced_conflicts=None,
    )
    assert result["valid"]
    assert result["warnings"]


def test_validator_warns_on_conflicts() -> None:
    result = validate_training_request(
        dataset_readiness=_ready(), dataset_decision="approve", rag_required=False, rag_decision=None,
        advanced_risk=None, advanced_conflicts={"conflict_count": 3},
    )
    assert result["valid"]
    assert any("conflicting-answer" in w for w in result["warnings"])


def test_validator_passes_clean_request() -> None:
    result = validate_training_request(
        dataset_readiness=_ready(), dataset_decision="approve", rag_required=True,
        rag_decision="approve", advanced_risk={"risk_items": [], "risk_item_count": 0},
        advanced_conflicts={"conflict_count": 0},
    )
    assert result["valid"]
    assert result["blockers"] == []
    assert result["warnings"] == []


# -- training_request_builder ---------------------------------------------------


def test_available_profiles_matches_dict_keys() -> None:
    assert available_profiles() == sorted(HYPERPARAMETER_PROFILES)


def test_build_training_request_default_profile_shape() -> None:
    payload = build_training_request(
        name="job-1", dataset_version_public_id="dv1", tokenizer_version_public_id="tv1",
        core_model_version_public_id="cv1",
    )
    assert payload["name"] == "job-1"
    assert payload["job_mode"] == "smoke_pretraining"
    assert payload["configuration"] == HYPERPARAMETER_PROFILES["default"]
    # must not share the module-level dict instance (mutation safety)
    assert payload["configuration"] is not HYPERPARAMETER_PROFILES["default"]


def test_build_training_request_unknown_profile_raises() -> None:
    try:
        build_training_request(
            name="x", dataset_version_public_id="dv", tokenizer_version_public_id="tv",
            core_model_version_public_id="cv", hyperparameter_profile="nonexistent",
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "nonexistent" in str(exc)


# -- training_result_analyzer ----------------------------------------------------


def test_analyze_training_result_detects_overfitting() -> None:
    job = {"status": "completed", "initial_training_loss": 3.0, "latest_training_loss": 1.0, "latest_validation_loss": 3.0}
    result = analyze_training_result(job=job, step_losses=[3.0, 2.5, 2.0, 1.5, 1.0], checkpoints=[])
    assert any(i.startswith("overfitting_signal") for i in result["indicators"])
    assert result["failed"] is False


def test_analyze_training_result_detects_underfitting() -> None:
    job = {"status": "completed", "initial_training_loss": 3.0, "latest_training_loss": 2.95, "latest_validation_loss": 2.96}
    result = analyze_training_result(job=job, step_losses=[3.0, 2.98, 2.97, 2.96, 2.95], checkpoints=[])
    assert any(i.startswith("underfitting_signal") for i in result["indicators"])


def test_analyze_training_result_detects_divergence() -> None:
    # is_diverging() needs >= 10 points (default window=5): early-window avg vs late-window avg.
    step_losses = [1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0, 2.0, 2.0]
    job = {"status": "completed", "initial_training_loss": 1.0, "latest_training_loss": 2.0, "latest_validation_loss": 2.1}
    result = analyze_training_result(job=job, step_losses=step_losses, checkpoints=[])
    assert any(i.startswith("divergence_signal") for i in result["indicators"])
    assert result["diverging"] is True


def test_analyze_training_result_flags_failed_job() -> None:
    job = {"status": "failed", "initial_training_loss": None, "latest_training_loss": None, "latest_validation_loss": None}
    result = analyze_training_result(job=job, step_losses=[], checkpoints=[])
    assert result["failed"] is True
    assert result["job_status"] == "failed"


def test_analyze_training_result_checkpoint_summary() -> None:
    job = {"status": "completed", "initial_training_loss": 2.0, "latest_training_loss": 0.5, "latest_validation_loss": 0.6}
    checkpoints = [{"status": "verified"}, {"status": "verified"}, {"status": "corrupt"}]
    result = analyze_training_result(job=job, step_losses=[2.0, 1.0, 0.5], checkpoints=checkpoints)
    assert result["checkpoint_summary"] == {"total": 3, "verified": 2, "corrupt": 1}


def test_analyze_training_result_clean_run_has_no_indicators() -> None:
    job = {"status": "completed", "initial_training_loss": 3.0, "latest_training_loss": 0.5, "latest_validation_loss": 0.6}
    result = analyze_training_result(job=job, step_losses=[3.0, 2.0, 1.0, 0.5], checkpoints=[{"status": "verified"}])
    assert result["indicators"] == []


# -- model_comparator ------------------------------------------------------------


def _metric(language, category, name, value):
    return {"language": language, "category": category, "metric_name": name, "metric_value": value}


def test_compare_models_detects_improvement_for_higher_is_better() -> None:
    previous = [_metric("en", "reasoning", "accuracy", 0.70)]
    new = [_metric("en", "reasoning", "accuracy", 0.80)]
    result = compare_models(previous_metrics=previous, new_metrics=new)
    assert result["improvement_count"] == 1
    assert result["comparisons"][0]["classification"] == "improvement"


def test_compare_models_detects_regression_for_higher_is_better() -> None:
    previous = [_metric("en", "reasoning", "accuracy", 0.80)]
    new = [_metric("en", "reasoning", "accuracy", 0.70)]
    result = compare_models(previous_metrics=previous, new_metrics=new)
    assert result["regression_count"] == 1


def test_compare_models_lower_is_better_metric_inverted() -> None:
    previous = [_metric("en", "latency", "latency_ms", 100)]
    new = [_metric("en", "latency", "latency_ms", 200)]
    result = compare_models(previous_metrics=previous, new_metrics=new)
    # latency went up (worse) -> regression, even though the raw number increased
    assert result["comparisons"][0]["classification"] == "regression"


def test_compare_models_neutral_within_threshold() -> None:
    previous = [_metric("en", "reasoning", "accuracy", 0.80)]
    new = [_metric("en", "reasoning", "accuracy", 0.805)]
    result = compare_models(previous_metrics=previous, new_metrics=new)
    assert result["comparisons"][0]["classification"] == "neutral"


def test_compare_models_no_data_when_metric_missing_from_one_side() -> None:
    previous = [_metric("en", "reasoning", "accuracy", 0.80)]
    new: list[dict] = []
    result = compare_models(previous_metrics=previous, new_metrics=new)
    assert result["no_data_count"] == 1
    assert result["comparisons"][0]["classification"] == "no_data"


def test_compare_models_reports_missing_requested_categories() -> None:
    result = compare_models(previous_metrics=[], new_metrics=[])
    assert set(result["requested_categories_without_real_data"]) == {
        "tamil", "english", "reasoning", "coding", "mathematics", "science", "memory", "safety", "latency",
    }


# -- recommendation_engine -------------------------------------------------------


def test_recommendation_engine_flags_not_ready_dataset() -> None:
    recs = generate_learning_recommendations(
        dataset_readiness=_ready(status="Not Ready", reasons=["too few records"]),
        advanced_report=None, rag_report=None, training_result=None, comparison=None,
    )
    assert any(r["confidence"] == "high" and "dataset" in r["action"].lower() for r in recs)


def test_recommendation_engine_flags_rag_blocked() -> None:
    recs = generate_learning_recommendations(
        dataset_readiness=_ready(), advanced_report=None,
        rag_report={"production_rag_readiness": "blocked", "blocking_reasons": ["x"], "threshold_evaluation": []},
        training_result=None, comparison=None,
    )
    assert any("RAG" in r["action"] and r["confidence"] == "high" for r in recs)


def test_recommendation_engine_flags_failed_training() -> None:
    recs = generate_learning_recommendations(
        dataset_readiness=_ready(), advanced_report=None, rag_report=None,
        training_result={"failed": True, "job_status": "failed", "indicators": []}, comparison=None,
    )
    assert any(r["action"] == "Retrain" for r in recs)


def test_recommendation_engine_flags_benchmark_regression() -> None:
    recs = generate_learning_recommendations(
        dataset_readiness=_ready(), advanced_report=None, rag_report=None, training_result=None,
        comparison={
            "regression_count": 1,
            "comparisons": [{"classification": "regression", "language": "en", "category": "reasoning", "metric_name": "accuracy"}],
            "requested_categories_without_real_data": [],
        },
    )
    assert any(r["confidence"] == "high" and "regress" in r["action"].lower() for r in recs)


def test_recommendation_engine_safe_for_release_when_nothing_blocking() -> None:
    recs = generate_learning_recommendations(
        dataset_readiness=_ready(), advanced_report=None, rag_report=None, training_result=None, comparison=None,
    )
    assert len(recs) == 1
    assert recs[0]["action"] == "Safe for release review"


def test_every_recommendation_has_why_evidence_confidence() -> None:
    recs = generate_learning_recommendations(
        dataset_readiness=_ready(status="Not Ready", reasons=["x"]), advanced_report=None,
        rag_report=None, training_result=None, comparison=None,
    )
    for rec in recs:
        assert set(rec) == {"action", "why", "evidence", "confidence"}
        assert rec["why"]
        assert rec["confidence"] in {"high", "medium", "low"}


# -- learning_report_generator ---------------------------------------------------


def test_generate_learning_report_marks_sections_present() -> None:
    report = generate_learning_report(
        session_public_id="s1", dataset_report={"a": 1}, rag_report=None,
        training_report={"b": 2}, benchmark_report=None, comparison_report=None,
        recommendations=[{"action": "Safe for release review", "why": "x", "evidence": {}, "confidence": "medium"}],
    )
    assert report["sections_present"] == {
        "dataset_report": True, "rag_report": False, "training_report": True,
        "benchmark_report": False, "comparison_report": False,
    }
    assert report["has_high_confidence_blocking_findings"] is False


def test_generate_learning_report_flags_high_confidence_blocking() -> None:
    report = generate_learning_report(
        session_public_id="s1", dataset_report=None, rag_report=None, training_report=None,
        benchmark_report=None, comparison_report=None,
        recommendations=[
            {"action": "Retrain", "why": "x", "evidence": {}, "confidence": "high"},
            {"action": "Safe for release review", "why": "y", "evidence": {}, "confidence": "medium"},
        ],
    )
    assert report["has_high_confidence_blocking_findings"] is True
    assert report["blocking_recommendation_count"] == 1
