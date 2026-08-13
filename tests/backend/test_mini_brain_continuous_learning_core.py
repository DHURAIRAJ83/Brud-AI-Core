"""MB-08: pure-module unit tests for
core_model/mini_brain/continuous_learning/."""

from core_model.mini_brain.continuous_learning.continuous_learning_report import (
    generate_continuous_learning_report,
)
from core_model.mini_brain.continuous_learning.dataset_recommendation import recommend_datasets
from core_model.mini_brain.continuous_learning.difficulty_analyzer import (
    analyze_difficulty,
    classify_difficulty,
)
from core_model.mini_brain.continuous_learning.failure_analyzer import analyze_failures
from core_model.mini_brain.continuous_learning.feedback_collector import collect_feedback
from core_model.mini_brain.continuous_learning.hallucination_detector import detect_hallucinations
from core_model.mini_brain.continuous_learning.knowledge_gap_detector import detect_knowledge_gaps
from core_model.mini_brain.continuous_learning.priority_engine import rank_priorities
from core_model.mini_brain.continuous_learning.training_recommendation import (
    recommend_training_action,
)
from core_model.mini_brain.continuous_learning.weak_topic_detector import detect_weak_topics


def _routing_event(**overrides):
    base = {
        "request_id": "r1", "resolved_route": "core_model", "route_status": "executable",
        "evidence_status": "grounded", "safety_status": "safe", "error_code": None,
    }
    base.update(overrides)
    return base


def _feedback_event(**overrides):
    base = {"request_id": "r1", "feedback_type": "thumbs_up"}
    base.update(overrides)
    return base


def _case(**overrides):
    base = {
        "event_type": "knowledge_gap", "domain": "History", "intent": "facts",
        "reason_codes": [], "priority_score": 10.0, "priority_band": "medium",
        "content_unavailable_for_review": False, "canonical_question": "What year?",
    }
    base.update(overrides)
    return base


# -- feedback_collector -------------------------------------------------------------


def test_collect_feedback_counts_unanswered_and_feedback_types() -> None:
    events = [
        _routing_event(request_id="r1", resolved_route="core_model"),
        _routing_event(request_id="r2", resolved_route="clarify"),
        _routing_event(request_id="r3", resolved_route="refuse"),
    ]
    feedback = [_feedback_event(request_id="r1", feedback_type="thumbs_up"),
                _feedback_event(request_id="r2", feedback_type="thumbs_down")]
    result = collect_feedback(routing_events=events, feedback_events=feedback)
    assert result["total_conversations_observed"] == 3
    assert result["unanswered_count"] == 2
    assert result["positive_feedback_count"] == 1
    assert result["negative_feedback_count"] == 1


def test_collect_feedback_handles_empty_input() -> None:
    result = collect_feedback(routing_events=[], feedback_events=[])
    assert result["total_conversations_observed"] == 0
    assert result["unanswered_rate"] is None


# -- failure_analyzer ----------------------------------------------------------------


def test_failure_analyzer_detects_no_answer() -> None:
    events = [_routing_event(resolved_route="insufficient")]
    result = analyze_failures(routing_events=events, feedback_events=[])
    assert result["failure_counts"]["no_answer"] == 1
    assert result["failure_rate"] == 1.0


def test_failure_analyzer_detects_blocked_answer() -> None:
    events = [_routing_event(route_status="blocked", safety_status="output_blocked")]
    result = analyze_failures(routing_events=events, feedback_events=[])
    assert result["failure_counts"]["blocked_answer"] == 1


def test_failure_analyzer_detects_timeout() -> None:
    events = [_routing_event(error_code="upstream_timeout_error")]
    result = analyze_failures(routing_events=events, feedback_events=[])
    assert result["failure_counts"]["timeout"] == 1
    assert result["failure_counts"]["other_error"] == 0


def test_failure_analyzer_detects_other_error_distinct_from_timeout() -> None:
    events = [_routing_event(error_code="upstream_5xx")]
    result = analyze_failures(routing_events=events, feedback_events=[])
    assert result["failure_counts"]["other_error"] == 1
    assert result["failure_counts"]["timeout"] == 0


def test_failure_analyzer_detects_low_confidence() -> None:
    events = [_routing_event(evidence_status="none")]
    result = analyze_failures(routing_events=events, feedback_events=[])
    assert result["failure_counts"]["low_confidence"] == 1


def test_failure_analyzer_detects_wrong_answer_via_thumbs_down() -> None:
    events = [_routing_event(request_id="r9")]
    feedback = [_feedback_event(request_id="r9", feedback_type="thumbs_down")]
    result = analyze_failures(routing_events=events, feedback_events=feedback)
    assert result["failure_counts"]["wrong_answer"] == 1


def test_failure_rate_never_exceeds_one_even_with_multiple_signals_per_conversation() -> None:
    # a single conversation triggering several categories at once must
    # still only count once toward failure_rate (bounded [0,1])
    events = [_routing_event(
        request_id="r1", resolved_route="insufficient", route_status="blocked",
        safety_status="output_blocked", evidence_status="none", error_code="timeout",
    )]
    feedback = [_feedback_event(request_id="r1", feedback_type="thumbs_down")]
    result = analyze_failures(routing_events=events, feedback_events=feedback)
    assert result["failure_rate"] == 1.0
    assert result["total_failure_signals"] > result["failed_conversation_count"]


def test_failure_analyzer_no_failures_gives_zero_rate() -> None:
    events = [_routing_event()]
    result = analyze_failures(routing_events=events, feedback_events=[])
    assert result["failure_rate"] == 0.0
    assert result["dominant_failure_category"] is None


# -- hallucination_detector -----------------------------------------------------------


def test_hallucination_detector_classifies_unsupported_claims() -> None:
    events = [_routing_event(evidence_status="model_only"), _routing_event(evidence_status="none")]
    result = detect_hallucinations(routing_events=events)
    assert result["unsupported_claim_count"] == 2
    assert result["hallucination_rate"] == 1.0


def test_hallucination_detector_classifies_missing_citations() -> None:
    events = [_routing_event(evidence_status="insufficient")]
    result = detect_hallucinations(routing_events=events)
    assert result["missing_citation_count"] == 1


def test_hallucination_detector_classifies_inconsistent_answers() -> None:
    events = [_routing_event(evidence_status="conflicting")]
    result = detect_hallucinations(routing_events=events)
    assert result["inconsistent_answer_count"] == 1


def test_hallucination_detector_grounded_answers_are_not_flagged() -> None:
    events = [_routing_event(evidence_status="grounded"), _routing_event(evidence_status="partially_grounded")]
    result = detect_hallucinations(routing_events=events)
    assert result["hallucination_signal_count"] == 0
    assert result["grounded_count"] == 2


# -- knowledge_gap_detector -----------------------------------------------------------


def test_knowledge_gap_detector_groups_by_domain_and_intent() -> None:
    cases = [
        _case(domain="History", intent="dates"),
        _case(domain="History", intent="facts"),
        _case(domain="Math", intent="algebra"),
        _case(event_type="language_failure", domain="Ignored"),
    ]
    result = detect_knowledge_gaps(knowledge_gap_cases=cases)
    assert result["total_knowledge_gap_cases"] == 3
    domains = {d["domain"]: d["case_count"] for d in result["missing_domains"]}
    assert domains == {"History": 2, "Math": 1}


def test_knowledge_gap_detector_classifies_documentation_vs_workflow() -> None:
    cases = [
        _case(domain="A", reason_codes=["rag_content_missing"]),
        _case(domain="B", reason_codes=["domain_understanding_missing"]),
    ]
    result = detect_knowledge_gaps(knowledge_gap_cases=cases)
    assert result["missing_documentation_domains"] == ["A"]
    assert result["missing_workflow_domains"] == ["B"]


# -- weak_topic_detector ---------------------------------------------------------------


def test_weak_topic_detector_classifies_high_case_count_as_weak() -> None:
    cases = [_case(domain="History", priority_score=20) for _ in range(5)]
    result = detect_weak_topics(knowledge_gap_cases=cases)
    assert result["topics"][0]["domain"] == "History"
    assert result["topics"][0]["classification"] == "Weak"
    assert "History" in result["weak_topics"]


def test_weak_topic_detector_classifies_low_case_count_as_strong() -> None:
    cases = [_case(domain="Math", priority_score=5)]
    result = detect_weak_topics(knowledge_gap_cases=cases)
    assert result["topics"][0]["classification"] == "Strong"
    assert "Math" in result["strong_topics"]


def test_weak_topic_detector_sorts_by_weakness_descending() -> None:
    cases = [_case(domain="Weak1", priority_score=20)] * 5 + [_case(domain="Weak2", priority_score=5)]
    result = detect_weak_topics(knowledge_gap_cases=cases)
    assert result["topics"][0]["weakness_index"] >= result["topics"][-1]["weakness_index"]


# -- difficulty_analyzer ----------------------------------------------------------------


def test_classify_difficulty_unknown_for_missing_text() -> None:
    assert classify_difficulty(None) == "Unknown"
    assert classify_difficulty("") == "Unknown"
    assert classify_difficulty("   ") == "Unknown"


def test_classify_difficulty_easy_for_short_text() -> None:
    assert classify_difficulty("What is this?") == "Easy"


def test_classify_difficulty_expert_relabels_very_hard() -> None:
    long_advanced_text = " ".join(["asymptotic", "eigenvalue", "polymorphism"] * 25)
    assert classify_difficulty(long_advanced_text) == "Expert"


def test_analyze_difficulty_marks_unavailable_content_as_unknown() -> None:
    cases = [_case(content_unavailable_for_review=True, canonical_question="something")]
    result = analyze_difficulty(knowledge_gap_cases=cases)
    assert result["distribution"]["Unknown"] == 1


def test_analyze_difficulty_empty_cases() -> None:
    result = analyze_difficulty(knowledge_gap_cases=[])
    assert result["total_cases_classified"] == 0
    assert result["hard_or_expert_ratio"] is None


# -- dataset_recommendation --------------------------------------------------------------


def test_recommend_datasets_only_for_weak_topics() -> None:
    weak_topics = [
        {"domain": "History", "case_count": 5, "weakness_index": 50.0, "classification": "Weak"},
        {"domain": "Math", "case_count": 1, "weakness_index": 10.0, "classification": "Strong"},
    ]
    result = recommend_datasets(
        weak_topics=weak_topics, missing_documentation_domains=["History"], missing_workflow_domains=[],
    )
    assert len(result["recommendations"]) == 1
    assert result["recommendations"][0]["domain"] == "History"
    formats = {f["format"] for f in result["recommendations"][0]["recommended_formats"]}
    assert "Documentation" in formats
    assert "PDFs" in formats


def test_recommend_datasets_severe_weakness_adds_books() -> None:
    weak_topics = [{"domain": "X", "case_count": 10, "weakness_index": 75.0, "classification": "Weak"}]
    result = recommend_datasets(weak_topics=weak_topics, missing_documentation_domains=[], missing_workflow_domains=[])
    formats = {f["format"] for f in result["recommendations"][0]["recommended_formats"]}
    assert "Books" in formats


def test_recommend_datasets_every_recommendation_has_why() -> None:
    weak_topics = [{"domain": "X", "case_count": 2, "weakness_index": 35.0, "classification": "Weak"}]
    result = recommend_datasets(weak_topics=weak_topics, missing_documentation_domains=[], missing_workflow_domains=[])
    for fmt in result["recommendations"][0]["recommended_formats"]:
        assert fmt["why"]


# -- training_recommendation ---------------------------------------------------------------


def test_training_recommendation_no_training_when_healthy() -> None:
    result = recommend_training_action(
        failure_rate=0.01, hallucination_rate=0.01, weak_topics=[], training_eligible_case_count=0,
    )
    assert result["action"] == "No Training"
    assert result["why"]


def test_training_recommendation_full_retraining_when_severe() -> None:
    weak_topics = [{"domain": f"d{i}", "weakness_index": 70.0, "classification": "Weak"} for i in range(3)]
    result = recommend_training_action(
        failure_rate=0.5, hallucination_rate=0.4, weak_topics=weak_topics, training_eligible_case_count=10,
    )
    assert result["action"] == "Full Retraining"


def test_training_recommendation_continue_training_with_eligible_cases() -> None:
    result = recommend_training_action(
        failure_rate=0.15, hallucination_rate=0.1, weak_topics=[], training_eligible_case_count=6,
    )
    assert result["action"] == "Continue Training"


def test_training_recommendation_fine_tune_as_middle_ground() -> None:
    result = recommend_training_action(
        failure_rate=0.15, hallucination_rate=0.1, weak_topics=[], training_eligible_case_count=0,
    )
    assert result["action"] == "Fine Tune"


def test_training_recommendation_always_has_evidence() -> None:
    result = recommend_training_action(
        failure_rate=0.2, hallucination_rate=0.2, weak_topics=[], training_eligible_case_count=1,
    )
    assert "evidence" in result
    assert result["evidence"]["failure_rate"] == 0.2


# -- priority_engine -----------------------------------------------------------------------


def test_priority_engine_assigns_dominant_band_per_domain() -> None:
    recs = [{"domain": "History", "case_count": 2}]
    cases = [_case(domain="History", priority_band="critical"), _case(domain="History", priority_band="low")]
    training_rec = {"action": "Fine Tune", "why": "x", "evidence": {}}
    result = rank_priorities(dataset_recommendations=recs, knowledge_gap_cases=cases, training_recommendation=training_rec)
    assert result["dataset_recommendations"][0]["priority"] == "Critical"


def test_priority_engine_maps_informational_to_low() -> None:
    recs = [{"domain": "X", "case_count": 1}]
    cases = [_case(domain="X", priority_band="informational")]
    result = rank_priorities(dataset_recommendations=recs, knowledge_gap_cases=cases, training_recommendation={"action": "No Training"})
    assert result["dataset_recommendations"][0]["priority"] == "Low"


def test_priority_engine_sorts_recommendations_by_priority_descending() -> None:
    recs = [{"domain": "Low1"}, {"domain": "Crit1"}]
    cases = [_case(domain="Low1", priority_band="low"), _case(domain="Crit1", priority_band="critical")]
    result = rank_priorities(dataset_recommendations=recs, knowledge_gap_cases=cases, training_recommendation={"action": "No Training"})
    assert result["dataset_recommendations"][0]["domain"] == "Crit1"


def test_priority_engine_training_recommendation_inherits_overall_highest_band() -> None:
    cases = [_case(domain="A", priority_band="low"), _case(domain="B", priority_band="critical")]
    result = rank_priorities(dataset_recommendations=[], knowledge_gap_cases=cases, training_recommendation={"action": "Full Retraining"})
    assert result["training_recommendation"]["priority"] == "Critical"


# -- continuous_learning_report -------------------------------------------------------------


def _minimal_reports():
    return {
        "feedback_report": {"total_conversations_observed": 10},
        "failure_report": {"failure_rate": 0.02, "failure_counts": {}},
        "hallucination_report": {"hallucination_rate": 0.02, "unsupported_claim_count": 0, "missing_citation_count": 0, "inconsistent_answer_count": 0},
        "knowledge_gap_report": {"total_knowledge_gap_cases": 0, "missing_domains": [], "missing_documentation_count": 0, "missing_workflow_count": 0},
        "weak_topic_report": {"weak_topics": [], "strong_topics": ["Math"]},
        "difficulty_report": {"distribution": {"Easy": 5}},
        "dataset_recommendation_report": {"recommendations": [], "domains_needing_data": []},
        "training_recommendation": {"action": "No Training", "why": "healthy"},
    }


def test_report_healthy_when_metrics_are_low_and_no_weak_topics() -> None:
    reports = _minimal_reports()
    report = generate_continuous_learning_report(session_public_id="s1", **reports)
    assert report["overall_health"] == "Healthy"
    assert "No action recommended" in report["improvement_plan"][0]


def test_report_at_risk_when_failure_rate_is_severe() -> None:
    reports = _minimal_reports()
    reports["failure_report"] = {"failure_rate": 0.5, "failure_counts": {}}
    report = generate_continuous_learning_report(session_public_id="s1", **reports)
    assert report["overall_health"] == "At Risk"


def test_report_includes_improvement_plan_for_weak_domains_and_training() -> None:
    reports = _minimal_reports()
    reports["dataset_recommendation_report"] = {
        "recommendations": [{"domain": "History"}], "domains_needing_data": ["History"],
    }
    reports["training_recommendation"] = {"action": "Fine Tune", "why": "elevated metrics"}
    report = generate_continuous_learning_report(session_public_id="s1", **reports)
    assert any("History" in step for step in report["improvement_plan"])
    assert any("Fine Tune" in step for step in report["improvement_plan"])
