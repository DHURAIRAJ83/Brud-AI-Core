"""MB-12: pure-module unit tests for
core_model/mini_brain/pipeline_coordinator/."""

from core_model.mini_brain.pipeline_coordinator.admin_decision_center import (
    DECISIONS,
    evaluate_decision,
)
from core_model.mini_brain.pipeline_coordinator.dependency_coordinator import check_dependencies
from core_model.mini_brain.pipeline_coordinator.improvement_predictor import predict_improvement
from core_model.mini_brain.pipeline_coordinator.lifecycle_timeline import build_timeline
from core_model.mini_brain.pipeline_coordinator.master_report_generator import (
    generate_master_report,
)
from core_model.mini_brain.pipeline_coordinator.pipeline_manager import track_pipeline
from core_model.mini_brain.pipeline_coordinator.rag_first_enforcement import check_rag_gate
from core_model.mini_brain.pipeline_coordinator.recommendation_engine import recommend_next_action
from core_model.mini_brain.pipeline_coordinator.state_machine import (
    STAGE_ORDER,
    is_allowed_alternate_transition,
    is_one_step_forward,
    stage_index,
)
from core_model.mini_brain.pipeline_coordinator.training_readiness_coordinator import (
    coordinate_training_readiness,
)

# -- state_machine --------------------------------------------------------------------


def test_stage_order_has_twelve_named_states() -> None:
    assert len(STAGE_ORDER) == 12
    assert STAGE_ORDER[0] == "new"
    assert STAGE_ORDER[-1] == "archived"


def test_is_one_step_forward() -> None:
    assert is_one_step_forward(current_stage="new", target_stage="under_research")
    assert not is_one_step_forward(current_stage="new", target_stage="draft_ready")


def test_allowed_alternate_transitions() -> None:
    assert is_allowed_alternate_transition(current_stage="under_research", target_stage="draft_ready")
    assert is_allowed_alternate_transition(current_stage="rag_testing", target_stage="dataset_planned")
    assert not is_allowed_alternate_transition(current_stage="new", target_stage="draft_ready")


def test_stage_index() -> None:
    assert stage_index("new") == 0
    assert stage_index("archived") == 11


# -- dependency_coordinator -------------------------------------------------------------


def test_check_dependencies_blocks_same_stage() -> None:
    result = check_dependencies(current_stage="new", target_stage="new", evidence={})
    assert not result["allowed"]


def test_check_dependencies_allows_one_step_forward_with_evidence() -> None:
    result = check_dependencies(current_stage="new", target_stage="under_research", evidence={"mb09_linked": True})
    assert result["allowed"]


def test_check_dependencies_blocks_missing_evidence() -> None:
    result = check_dependencies(current_stage="new", target_stage="under_research", evidence={"mb09_linked": False})
    assert not result["allowed"]
    assert "missing required evidence: mb09_linked" in result["reasons"]


def test_check_dependencies_blocks_skipping_stages() -> None:
    result = check_dependencies(current_stage="new", target_stage="dataset_planned", evidence={"mb11_linked": True})
    assert not result["allowed"]
    assert any("cannot move" in r for r in result["reasons"])


def test_check_dependencies_allows_local_draft_skip() -> None:
    result = check_dependencies(current_stage="under_research", target_stage="draft_ready", evidence={"mb10_linked": True})
    assert result["allowed"]


def test_check_dependencies_allows_rag_gate_failure_bounce_back() -> None:
    result = check_dependencies(current_stage="rag_testing", target_stage="dataset_planned", evidence={"mb11_linked": True})
    assert result["allowed"]


def test_check_dependencies_archive_always_allowed() -> None:
    result = check_dependencies(current_stage="training_running", target_stage="archived", evidence={})
    assert result["allowed"]


# -- pipeline_manager ------------------------------------------------------------------


def test_track_pipeline_completion_percent() -> None:
    result = track_pipeline(
        public_chat_activity=True, knowledge_gap_flagged=True, mb09_linked=True, mb10_consensus_done=True,
        mb11_linked=True, rag_validated=True, mb06_linked=True, release_candidate_present=True,
    )
    assert result["completion_percent"] == 100.0
    assert result["remaining_steps"] == []


def test_track_pipeline_none_done() -> None:
    result = track_pipeline(
        public_chat_activity=False, knowledge_gap_flagged=False, mb09_linked=False, mb10_consensus_done=False,
        mb11_linked=False, rag_validated=False, mb06_linked=False, release_candidate_present=False,
    )
    assert result["completion_percent"] == 0.0
    assert len(result["remaining_steps"]) == 8


# -- rag_first_enforcement ---------------------------------------------------------------


def test_check_rag_gate_no_report_fails() -> None:
    result = check_rag_gate(rag_report=None, admin_decision=None)
    assert result["passed"] is False
    assert result["recommendation"] == "return_to_dataset_evolution"


def test_check_rag_gate_passes_with_good_report_and_approval() -> None:
    report = {
        "production_rag_readiness": "potentially_ready",
        "citation_metrics": {"citation_validity_rate": 0.9},
        "threshold_evaluation": [{"dimension": "maximum_hallucination_rate", "passed": True}],
    }
    result = check_rag_gate(rag_report=report, admin_decision="approve")
    assert result["passed"] is True


def test_check_rag_gate_fails_on_blocked_readiness() -> None:
    report = {"production_rag_readiness": "blocked", "citation_metrics": {}, "threshold_evaluation": []}
    result = check_rag_gate(rag_report=report, admin_decision="approve")
    assert result["passed"] is False
    assert any("blocked" in r for r in result["reasons"])


def test_check_rag_gate_fails_on_low_citation_validity() -> None:
    report = {
        "production_rag_readiness": "potentially_ready", "citation_metrics": {"citation_validity_rate": 0.3},
        "threshold_evaluation": [{"dimension": "maximum_hallucination_rate", "passed": True}],
    }
    result = check_rag_gate(rag_report=report, admin_decision="approve")
    assert result["passed"] is False


def test_check_rag_gate_fails_on_hallucination_threshold() -> None:
    report = {
        "production_rag_readiness": "potentially_ready", "citation_metrics": {"citation_validity_rate": 0.9},
        "threshold_evaluation": [{"dimension": "maximum_hallucination_rate", "passed": False}],
    }
    result = check_rag_gate(rag_report=report, admin_decision="approve")
    assert result["passed"] is False
    assert result["hallucination_check_passed"] is False


def test_check_rag_gate_fails_without_admin_approval() -> None:
    report = {
        "production_rag_readiness": "potentially_ready", "citation_metrics": {"citation_validity_rate": 0.9},
        "threshold_evaluation": [{"dimension": "maximum_hallucination_rate", "passed": True}],
    }
    result = check_rag_gate(rag_report=report, admin_decision=None)
    assert result["passed"] is False
    assert result["admin_approved"] is False


# -- training_readiness_coordinator ------------------------------------------------------


def test_coordinate_training_readiness_no_sources_available() -> None:
    result = coordinate_training_readiness(
        mb05_training_status=None, mb051_overall_score=None, mb06_quality_score=None,
        mb08_average_failure_rate=None, mb09_recurring_weak_domain_count=None, mb10_quality_score=None,
        mb11_predicted_quality_score=None,
    )
    assert result["sources_available"] == 0
    assert result["unified_readiness_score"] == 0.0
    assert result["status"] == "Not Ready"


def test_coordinate_training_readiness_all_sources_ready() -> None:
    result = coordinate_training_readiness(
        mb05_training_status="Ready", mb051_overall_score=90.0, mb06_quality_score=90.0,
        mb08_average_failure_rate=0.0, mb09_recurring_weak_domain_count=0, mb10_quality_score=90.0,
        mb11_predicted_quality_score=90.0,
    )
    assert result["sources_available"] == 7
    assert result["status"] == "Ready"


def test_coordinate_training_readiness_status_bands() -> None:
    needs_improvement = coordinate_training_readiness(
        mb05_training_status="Needs Improvement", mb051_overall_score=None, mb06_quality_score=None,
        mb08_average_failure_rate=None, mb09_recurring_weak_domain_count=None, mb10_quality_score=None,
        mb11_predicted_quality_score=None,
    )
    assert needs_improvement["status"] == "Needs Improvement"


# -- lifecycle_timeline -----------------------------------------------------------------


def test_build_timeline_sorts_chronologically() -> None:
    entries = [
        {"phase": "mb10", "event_type": "b", "message": "", "created_at": "2026-01-02 00:00:00"},
        {"phase": "mb09", "event_type": "a", "message": "", "created_at": "2026-01-01 00:00:00"},
    ]
    result = build_timeline(entries=entries)
    assert [e["phase"] for e in result["timeline"]] == ["mb09", "mb10"]
    assert result["first_event_at"] == "2026-01-01 00:00:00"
    assert result["last_event_at"] == "2026-01-02 00:00:00"


def test_build_timeline_empty() -> None:
    result = build_timeline(entries=[])
    assert result["event_count"] == 0
    assert result["first_event_at"] is None


# -- improvement_predictor ---------------------------------------------------------------


def test_predict_improvement_splits_language_gain() -> None:
    simulation = {
        "expected_benchmark_delta": 4.0, "expected_reasoning_delta": 2.0, "expected_language_delta": 10.0,
        "expected_memory_delta_mb": 20.0, "expected_rag_quality_delta": 6.0,
    }
    result = predict_improvement(mb11_simulation=simulation, mb06_comparison=None, tamil_percent=40.0, english_percent=60.0)
    assert result["expected_tamil_quality_gain"] == 4.0
    assert result["expected_english_quality_gain"] == 6.0
    assert result["expected_hallucination_reduction"] == 3.0


def test_predict_improvement_no_simulation_defaults_to_zero() -> None:
    result = predict_improvement(mb11_simulation=None, mb06_comparison=None, tamil_percent=None, english_percent=None)
    assert result["expected_benchmark_gain"] == 0.0
    assert result["expected_tamil_quality_gain"] is None


def test_predict_improvement_reports_real_mb06_comparison() -> None:
    result = predict_improvement(
        mb11_simulation=None, mb06_comparison={"improvement_count": 3, "regression_count": 1},
        tamil_percent=None, english_percent=None,
    )
    assert result["based_on_real_mb06_comparison"] is True
    assert result["mb06_improvement_count"] == 3


# -- admin_decision_center ---------------------------------------------------------------


def test_evaluate_decision_status_map_covers_all_nine() -> None:
    for decision in DECISIONS:
        result = evaluate_decision(decision=decision, current_stage="new", rag_gate_passed=None)
        assert result["decision"] == decision
        assert result["executes_nothing"] is True


def test_evaluate_decision_warns_on_premature_approve_training() -> None:
    result = evaluate_decision(decision="approve_training", current_stage="dataset_planned", rag_gate_passed=False)
    assert result["warnings"]


def test_evaluate_decision_no_warning_when_training_ready() -> None:
    result = evaluate_decision(decision="approve_training", current_stage="training_candidate", rag_gate_passed=True)
    assert result["warnings"] == []


def test_evaluate_decision_archive_sets_stage_override() -> None:
    result = evaluate_decision(decision="archive", current_stage="new", rag_gate_passed=None)
    assert result["stage_override"] == "archived"


def test_evaluate_decision_retry_rag_warns_if_already_passed() -> None:
    result = evaluate_decision(decision="retry_rag", current_stage="rag_testing", rag_gate_passed=True)
    assert result["warnings"]


# -- recommendation_engine ---------------------------------------------------------------


def _readiness(status="Ready", score=85.0, available=6, total=7):
    return {"status": status, "unified_readiness_score": score, "sources_available": available, "sources_total": total}


def test_recommend_next_action_improve_dataset_on_failed_rag_gate() -> None:
    rag_gate = {"passed": False, "reasons": ["blocked"]}
    result = recommend_next_action(
        current_stage="dataset_planned", rag_gate=rag_gate, training_readiness=_readiness(),
        pipeline_completion_percent=50.0, remaining_steps=[],
    )
    assert result["action"] == "improve_dataset"


def test_recommend_next_action_improve_dataset_on_not_ready() -> None:
    result = recommend_next_action(
        current_stage="dataset_planned", rag_gate=None, training_readiness=_readiness(status="Not Ready", score=10.0),
        pipeline_completion_percent=50.0, remaining_steps=[],
    )
    assert result["action"] == "improve_dataset"


def test_recommend_next_action_research_more_on_insufficient_evidence() -> None:
    result = recommend_next_action(
        current_stage="new", rag_gate=None, training_readiness=_readiness(status="Ready", score=90.0, available=1, total=7),
        pipeline_completion_percent=10.0, remaining_steps=["research"],
    )
    assert result["action"] == "research_more"


def test_recommend_next_action_approve_training_when_ready_at_training_candidate() -> None:
    result = recommend_next_action(
        current_stage="training_candidate", rag_gate={"passed": True, "reasons": []},
        training_readiness=_readiness(status="Ready", score=90.0, available=6, total=7),
        pipeline_completion_percent=90.0, remaining_steps=[],
    )
    assert result["action"] == "approve_training"


def test_recommend_next_action_continue_default() -> None:
    result = recommend_next_action(
        current_stage="draft_ready", rag_gate=None, training_readiness=_readiness(status="Ready", score=90.0, available=6, total=7),
        pipeline_completion_percent=50.0, remaining_steps=[],
    )
    assert result["action"] == "continue"


# -- master_report_generator -------------------------------------------------------------


def test_generate_master_report_ready_when_recommendation_present() -> None:
    report = generate_master_report(
        session_public_id="s1", topic="History", current_stage="dataset_planned",
        pipeline_manager_report={"completion_percent": 40.0, "completed_steps": [], "remaining_steps": []},
        rag_first_report=None, training_readiness_report={"status": "Ready", "unified_readiness_score": 90.0},
        recommendation_report={"action": "continue"}, dataset_health_score=80.0,
    )
    assert report["ready_for_admin_review"] is True
    assert report["next_action"] == "continue"
    assert any("only 40" in r for r in report["risks"])


def test_generate_master_report_not_ready_without_recommendation() -> None:
    report = generate_master_report(
        session_public_id="s1", topic="History", current_stage="new",
        pipeline_manager_report={"completion_percent": 0.0, "completed_steps": [], "remaining_steps": []},
        rag_first_report=None, training_readiness_report={"status": "Not Ready", "unified_readiness_score": 0.0},
        recommendation_report=None, dataset_health_score=None,
    )
    assert report["ready_for_admin_review"] is False
    assert report["next_action"] is None
