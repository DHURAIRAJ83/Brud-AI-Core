"""MB-11: pure-module unit tests for
core_model/mini_brain/dataset_evolution/."""

from core_model.mini_brain.dataset_evolution.coverage_analyzer import analyze_coverage_summary
from core_model.mini_brain.dataset_evolution.dependency_graph import analyze_dependencies
from core_model.mini_brain.dataset_evolution.evolution_analyzer import analyze_evolution
from core_model.mini_brain.dataset_evolution.evolution_report_generator import (
    generate_evolution_report,
)
from core_model.mini_brain.dataset_evolution.evolution_simulator import simulate_evolution
from core_model.mini_brain.dataset_evolution.expansion_planner import plan_expansion
from core_model.mini_brain.dataset_evolution.knowledge_factory_planner import (
    plan_knowledge_factory,
)
from core_model.mini_brain.dataset_evolution.quality_evolution import predict_quality_evolution
from core_model.mini_brain.dataset_evolution.recommendation_engine import recommend_evolution
from core_model.mini_brain.dataset_evolution.relationship_builder import build_relationships
from core_model.mini_brain.dataset_evolution.synthetic_dataset_planner import (
    plan_synthetic_dataset,
)
from core_model.mini_brain.dataset_evolution.version_planner import plan_version

# -- evolution_analyzer ---------------------------------------------------------------


def _mb08_report(weak=None, strong=None, failure_rate=0.1, hallucination_rate=0.05, missing=None):
    return {
        "weak_areas": weak or [], "strong_areas": strong or [], "failure_rate": failure_rate,
        "hallucination_rate": hallucination_rate,
        "knowledge_coverage": {"missing_domains": [{"domain": d} for d in (missing or [])]},
    }


def test_analyze_evolution_aggregates_weak_and_missing_domains() -> None:
    result = analyze_evolution(
        dataset_training={"status": "Ready"}, dataset_analysis={"records_analyzed": 100},
        advanced_report={"scores": {"overall": {"score": 80.0}}},
        mb08_reports=[_mb08_report(weak=["History"], missing=["Art"])],
        mb09_sessions=[{"knowledge_gap_evolution_report": {"recurring_weak_domains": [{"domain": "History"}]}}],
        mb10_sessions=[{"dataset_draft": {"topic": "History"}, "consensus_report": {"verdict": "strong_agreement"}}],
    )
    assert result["weak_domains"] == ["History"]
    assert result["missing_domains"] == ["Art"]
    assert result["research_drafts_available"] == 1
    assert result["provider_consensus_verdicts"] == ["strong_agreement"]


def test_analyze_evolution_empty_inputs_zero_pressure() -> None:
    result = analyze_evolution(
        dataset_training={"status": "Ready"}, dataset_analysis={"records_analyzed": 0},
        advanced_report={"scores": {"overall": {"score": 100.0}}},
        mb08_reports=[], mb09_sessions=[], mb10_sessions=[],
    )
    assert result["evolution_pressure"] == 0.0
    assert result["weak_domains"] == []


def test_analyze_evolution_pressure_caps_at_100() -> None:
    reports = [
        _mb08_report(weak=[f"D{i}" for i in range(20)], missing=[f"M{i}" for i in range(5)], failure_rate=1.0, hallucination_rate=1.0)
        for _ in range(3)
    ]
    result = analyze_evolution(
        dataset_training={"status": "Not Ready"}, dataset_analysis={"records_analyzed": 100},
        advanced_report={"scores": {"overall": {"score": 10.0}}},
        mb08_reports=reports, mb09_sessions=[], mb10_sessions=[],
    )
    assert result["evolution_pressure"] == 100.0


def test_analyze_evolution_respects_max_cycles_compared() -> None:
    reports = [_mb08_report(weak=[f"D{i}"]) for i in range(15)]
    result = analyze_evolution(
        dataset_training={"status": "Ready"}, dataset_analysis={"records_analyzed": 100},
        advanced_report={"scores": {"overall": {"score": 80.0}}},
        mb08_reports=reports, mb09_sessions=[], mb10_sessions=[],
    )
    assert result["cycles_compared"]["mb08"] == 10


# -- dependency_graph -----------------------------------------------------------------


def test_analyze_dependencies_detects_missing_dependency() -> None:
    graph = {
        "nodes": [{"id": "topic:A", "type": "topic", "label": "A"}], "edges": [],
    }
    result = analyze_dependencies(graph=graph)
    assert {"node_id": "topic:A", "reason": "topic has no subtopics"} in result["missing_dependencies"]


def test_analyze_dependencies_detects_broken_dependency() -> None:
    graph = {
        "nodes": [{"id": "topic:A", "type": "topic", "label": "A"}],
        "edges": [{"from": "topic:A", "to": "subtopic:missing", "relationship": "has_subtopic"}],
    }
    result = analyze_dependencies(graph=graph)
    assert result["broken_dependencies"]
    assert result["has_broken_or_circular"] is True


def test_analyze_dependencies_detects_circular_dependency() -> None:
    graph = {
        "nodes": [{"id": "a", "type": "topic", "label": "A"}, {"id": "b", "type": "subtopic", "label": "B"}],
        "edges": [{"from": "a", "to": "b", "relationship": "x"}, {"from": "b", "to": "a", "relationship": "y"}],
    }
    result = analyze_dependencies(graph=graph)
    assert result["circular_dependencies"]
    assert result["has_broken_or_circular"] is True


def test_analyze_dependencies_no_issues_on_clean_tree() -> None:
    graph = {
        "nodes": [
            {"id": "topic:A", "type": "topic", "label": "A"}, {"id": "subtopic:A:x", "type": "subtopic", "label": "x"},
            {"id": "lesson:1", "type": "lesson", "label": "1"},
        ],
        "edges": [
            {"from": "topic:A", "to": "subtopic:A:x", "relationship": "has_subtopic"},
            {"from": "subtopic:A:x", "to": "lesson:1", "relationship": "has_lesson"},
        ],
    }
    result = analyze_dependencies(graph=graph)
    assert result["broken_dependencies"] == []
    assert result["circular_dependencies"] == []
    assert "concept" in result["unpopulated_target_levels"]
    assert "topic" not in result["unpopulated_target_levels"]


def test_analyze_dependencies_empty_graph() -> None:
    result = analyze_dependencies(graph={"nodes": [], "edges": []})
    assert result["node_count"] == 0
    assert result["depth"] == 0
    assert result["populated_levels"] == []


# -- coverage_analyzer ----------------------------------------------------------------


def test_analyze_coverage_summary_classifies_all_tiers() -> None:
    result = analyze_coverage_summary(
        domain_coverage={
            "Excellent": {"coverage_percent": 90.0}, "Good": {"coverage_percent": 60.0},
            "NeedsExp": {"coverage_percent": 30.0}, "Critical": {"coverage_percent": 5.0},
        },
        language_distribution_percentages={"en": 100.0},
        difficulty_distribution={"Easy": 0, "Medium": 0, "Hard": 0, "Very Hard": 0},
        record_type_counts={}, curriculum_verdict_counts={},
    )
    assert result["by_domain"]["Excellent"]["classification"] == "Excellent"
    assert result["by_domain"]["Good"]["classification"] == "Good"
    assert result["by_domain"]["NeedsExp"]["classification"] == "Needs Expansion"
    assert result["by_domain"]["Critical"]["classification"] == "Critical Gap"


def test_analyze_coverage_summary_dataset_type_diversity() -> None:
    result = analyze_coverage_summary(
        domain_coverage={}, language_distribution_percentages={},
        difficulty_distribution={"Easy": 1}, record_type_counts={"instruction": 5, "conversation": 5},
        curriculum_verdict_counts={"Good Sequence": 1},
    )
    assert result["by_dataset_type"]["diversity_percent"] == 40.0


def test_analyze_coverage_summary_empty_difficulty_and_curriculum() -> None:
    result = analyze_coverage_summary(
        domain_coverage={}, language_distribution_percentages={}, difficulty_distribution={},
        record_type_counts={}, curriculum_verdict_counts={},
    )
    assert result["by_difficulty"]["balance_percent"] == 0.0
    assert result["by_knowledge_level"]["good_sequence_percent"] == 0.0
    assert result["dimensions_evaluated"] == 3


# -- relationship_builder --------------------------------------------------------------


def test_build_relationships_flags_disconnected_and_missing_evidence() -> None:
    result = build_relationships(
        duplicate_groups=[], conflict_groups=[], weak_domains=["History", "Math"],
        covered_domains=["Math"], research_backed_domains=["Math"],
    )
    assert result["disconnected_knowledge"] == ["History"]
    assert result["missing_evidence"] == ["History"]
    assert result["weak_evidence"] == []


def test_build_relationships_weak_evidence_when_researched_but_not_covered() -> None:
    result = build_relationships(
        duplicate_groups=[], conflict_groups=[], weak_domains=["History"],
        covered_domains=[], research_backed_domains=["History"],
    )
    assert result["weak_evidence"] == ["History"]
    assert result["missing_evidence"] == []


def test_build_relationships_health_score_penalizes_duplicates_and_conflicts() -> None:
    result = build_relationships(
        duplicate_groups=[["a", "b"]], conflict_groups=[{"key": "k"}], weak_domains=[],
        covered_domains=[], research_backed_domains=[],
    )
    assert result["relationship_health_score"] == 75.0
    assert result["broken_relationships"] is True


def test_build_relationships_healthy_when_all_covered_and_researched() -> None:
    result = build_relationships(
        duplicate_groups=[], conflict_groups=[], weak_domains=["Math"],
        covered_domains=["Math"], research_backed_domains=["Math"],
    )
    assert result["relationship_health_score"] == 100.0
    assert result["broken_relationships"] is False


# -- expansion_planner ------------------------------------------------------------------


def _coverage(critical=0, needs_expansion=0):
    return {"critical_gap_count": critical, "needs_expansion_count": needs_expansion}


def _relationships(dup_count=0):
    return {"duplicate_knowledge_count": dup_count, "duplicate_knowledge_groups": [], "missing_evidence": [], "conflicting_knowledge_groups": [], "conflicting_knowledge_count": 0}


def test_plan_expansion_replace_on_not_ready_high_duplicates() -> None:
    result = plan_expansion(
        dataset_status="Not Ready", duplicate_ratio=0.5, record_count=100,
        coverage_summary=_coverage(), relationship_report=_relationships(), evolution_pressure=50.0,
    )
    assert result["action"] == "replace"


def test_plan_expansion_create_new_on_many_critical_gaps() -> None:
    result = plan_expansion(
        dataset_status="Ready", duplicate_ratio=0.01, record_count=100,
        coverage_summary=_coverage(critical=3), relationship_report=_relationships(), evolution_pressure=50.0,
    )
    assert result["action"] == "create_new"


def test_plan_expansion_merge_on_duplicate_knowledge() -> None:
    result = plan_expansion(
        dataset_status="Ready", duplicate_ratio=0.01, record_count=100,
        coverage_summary=_coverage(), relationship_report=_relationships(dup_count=2), evolution_pressure=50.0,
    )
    assert result["action"] == "merge"


def test_plan_expansion_split_on_large_healthy_dataset() -> None:
    result = plan_expansion(
        dataset_status="Ready", duplicate_ratio=0.01, record_count=2000,
        coverage_summary=_coverage(), relationship_report=_relationships(), evolution_pressure=50.0,
    )
    assert result["action"] == "split"


def test_plan_expansion_archive_on_stagnant_low_pressure() -> None:
    result = plan_expansion(
        dataset_status="Needs Improvement", duplicate_ratio=0.01, record_count=100,
        coverage_summary=_coverage(), relationship_report=_relationships(), evolution_pressure=2.0,
    )
    assert result["action"] == "archive"


def test_plan_expansion_extend_default() -> None:
    result = plan_expansion(
        dataset_status="Ready", duplicate_ratio=0.01, record_count=100,
        coverage_summary=_coverage(), relationship_report=_relationships(), evolution_pressure=50.0,
    )
    assert result["action"] == "extend"


# -- version_planner ---------------------------------------------------------------------


def test_plan_version_growth_and_risk_per_action() -> None:
    extend = plan_version(current_record_count=100, expansion_action="extend")
    assert extend["predicted_record_count"] == 115
    assert extend["risk"] == "Low"

    replace = plan_version(current_record_count=100, expansion_action="replace")
    assert replace["predicted_record_count"] == 100
    assert replace["risk"] == "High"
    assert any("replace" in note for note in replace["migration_notes"])

    split = plan_version(current_record_count=100, expansion_action="split")
    assert split["predicted_record_count"] == 70


def test_plan_version_never_negative_record_count() -> None:
    result = plan_version(current_record_count=10, expansion_action="split")
    assert result["predicted_record_count"] >= 0


# -- knowledge_factory_planner ------------------------------------------------------------


def test_plan_knowledge_factory_recommends_documentation_on_critical_gap() -> None:
    result = plan_knowledge_factory(
        coverage_summary={
            "critical_gap_count": 1, "by_difficulty": {"classification": "Good"},
            "by_knowledge_level": {"classification": "Good"}, "by_dataset_type": {"classification": "Good"},
        },
        weak_domains=[], missing_domains=["Art"], advanced_overall_score=90.0,
    )
    types = [r["content_type"] for r in result["recommendations"]]
    assert "Documentation" in types


def test_plan_knowledge_factory_empty_fallback_is_testing_dataset() -> None:
    result = plan_knowledge_factory(
        coverage_summary={
            "critical_gap_count": 0, "by_difficulty": {"classification": "Excellent"},
            "by_knowledge_level": {"classification": "Excellent"}, "by_dataset_type": {"classification": "Excellent"},
        },
        weak_domains=[], missing_domains=[], advanced_overall_score=90.0,
    )
    assert result["recommendations"] == [{"content_type": "Testing Dataset", "why": (
        "no coverage gap was found -- a dedicated testing dataset is the lowest-risk way to confirm that before doing anything else"
    )}]


def test_plan_knowledge_factory_low_score_recommends_benchmarks() -> None:
    result = plan_knowledge_factory(
        coverage_summary={
            "critical_gap_count": 0, "by_difficulty": {"classification": "Good"},
            "by_knowledge_level": {"classification": "Good"}, "by_dataset_type": {"classification": "Good"},
        },
        weak_domains=[], missing_domains=[], advanced_overall_score=40.0,
    )
    types = [r["content_type"] for r in result["recommendations"]]
    assert "Benchmarks" in types and "Evaluation Sets" in types


# -- synthetic_dataset_planner ------------------------------------------------------------


def test_plan_synthetic_dataset_never_verified() -> None:
    result = plan_synthetic_dataset(target_domain="History", content_type="Documentation", predicted_record_count=1000)
    assert result["verified"] is False
    assert result["status"] == "design_only"
    assert result["expected_size"] == 100


def test_plan_synthetic_dataset_expected_size_floor() -> None:
    result = plan_synthetic_dataset(target_domain="History", content_type="FAQ", predicted_record_count=10)
    assert result["expected_size"] == 50


# -- quality_evolution ---------------------------------------------------------------------


def test_predict_quality_evolution_gain_by_action() -> None:
    result = predict_quality_evolution(
        current_advanced_score=50.0, expansion_action="replace", critical_gap_count=0,
        needs_expansion_count=0, knowledge_factory_content_types=[], growth_percent=0.0, cycles_compared=0,
    )
    assert result["quality_gain"] == 20.0
    assert result["predicted_quality_score"] == 70.0
    assert result["risk"] == "High"


def test_predict_quality_evolution_score_caps_at_100() -> None:
    result = predict_quality_evolution(
        current_advanced_score=95.0, expansion_action="replace", critical_gap_count=0,
        needs_expansion_count=0, knowledge_factory_content_types=[], growth_percent=0.0, cycles_compared=0,
    )
    assert result["predicted_quality_score"] == 100.0


def test_predict_quality_evolution_reasoning_gain_from_content_types() -> None:
    with_reasoning = predict_quality_evolution(
        current_advanced_score=50.0, expansion_action="extend", critical_gap_count=0,
        needs_expansion_count=0, knowledge_factory_content_types=["Reasoning Tasks"], growth_percent=0.0, cycles_compared=0,
    )
    without = predict_quality_evolution(
        current_advanced_score=50.0, expansion_action="extend", critical_gap_count=0,
        needs_expansion_count=0, knowledge_factory_content_types=["FAQ"], growth_percent=0.0, cycles_compared=0,
    )
    assert with_reasoning["reasoning_gain"] > without["reasoning_gain"]


def test_predict_quality_evolution_confidence_caps_at_90() -> None:
    result = predict_quality_evolution(
        current_advanced_score=50.0, expansion_action="extend", critical_gap_count=0,
        needs_expansion_count=0, knowledge_factory_content_types=[], growth_percent=0.0, cycles_compared=50,
    )
    assert result["confidence"] == 90.0


# -- evolution_simulator ---------------------------------------------------------------------


def test_simulate_evolution_derives_from_quality_evolution() -> None:
    qe = {"training_gain": 10.0, "coverage_gain": 20.0, "reasoning_gain": 5.0, "confidence": 70.0, "quality_gain": 8.0}
    result = simulate_evolution(quality_evolution=qe, expansion_action="extend")
    assert result["expected_improvement"] == 8.0
    assert result["expected_benchmark_delta"] == 4.0
    assert result["confidence"] == 70.0


# -- recommendation_engine ----------------------------------------------------------------


def _sim(confidence=70.0, improvement=10.0):
    return {"confidence": confidence, "expected_improvement": improvement}


def test_recommend_evolution_research_more_on_conflicts() -> None:
    result = recommend_evolution(
        evolution_pressure=50.0, expansion_action="extend", coverage_summary=_coverage(),
        relationship_report={"conflicting_knowledge_count": 1, "missing_evidence": []},
        simulation=_sim(), risk="Low",
    )
    assert result["recommendation"] == "research_more"


def test_recommend_evolution_collect_more_data_on_missing_evidence() -> None:
    result = recommend_evolution(
        evolution_pressure=50.0, expansion_action="extend", coverage_summary=_coverage(),
        relationship_report={"conflicting_knowledge_count": 0, "missing_evidence": ["Math"]},
        simulation=_sim(), risk="Low",
    )
    assert result["recommendation"] == "collect_more_data"


def test_recommend_evolution_reject_on_low_confidence_low_improvement() -> None:
    result = recommend_evolution(
        evolution_pressure=50.0, expansion_action="extend", coverage_summary=_coverage(),
        relationship_report={"conflicting_knowledge_count": 0, "missing_evidence": []},
        simulation=_sim(confidence=20.0, improvement=1.0), risk="Low",
    )
    assert result["recommendation"] == "reject"


def test_recommend_evolution_continue_current_dataset_when_healthy() -> None:
    result = recommend_evolution(
        evolution_pressure=1.0, expansion_action="extend", coverage_summary=_coverage(critical=0),
        relationship_report={"conflicting_knowledge_count": 0, "missing_evidence": []},
        simulation=_sim(confidence=80.0, improvement=10.0), risk="Low",
    )
    assert result["recommendation"] == "continue_current_dataset"


def test_recommend_evolution_wait_on_archive_action() -> None:
    result = recommend_evolution(
        evolution_pressure=50.0, expansion_action="archive", coverage_summary=_coverage(critical=1),
        relationship_report={"conflicting_knowledge_count": 0, "missing_evidence": []},
        simulation=_sim(confidence=80.0, improvement=10.0), risk="Low",
    )
    assert result["recommendation"] == "wait"


def test_recommend_evolution_replace_dataset_on_replace_action() -> None:
    result = recommend_evolution(
        evolution_pressure=50.0, expansion_action="replace", coverage_summary=_coverage(critical=1),
        relationship_report={"conflicting_knowledge_count": 0, "missing_evidence": []},
        simulation=_sim(confidence=80.0, improvement=10.0), risk="High",
    )
    assert result["recommendation"] == "replace_dataset"


def test_recommend_evolution_split_dataset_on_split_action() -> None:
    result = recommend_evolution(
        evolution_pressure=50.0, expansion_action="split", coverage_summary=_coverage(critical=1),
        relationship_report={"conflicting_knowledge_count": 0, "missing_evidence": []},
        simulation=_sim(confidence=80.0, improvement=10.0), risk="Medium",
    )
    assert result["recommendation"] == "split_dataset"


def test_recommend_evolution_expand_dataset_on_extend_merge_create_new() -> None:
    for action in ("extend", "merge", "create_new"):
        result = recommend_evolution(
            evolution_pressure=50.0, expansion_action=action, coverage_summary=_coverage(critical=1),
            relationship_report={"conflicting_knowledge_count": 0, "missing_evidence": []},
            simulation=_sim(confidence=80.0, improvement=10.0), risk="Medium",
        )
        assert result["recommendation"] == "expand_dataset"


# -- evolution_report_generator -----------------------------------------------------------


def test_generate_evolution_report_ready_when_recommendation_present() -> None:
    report = generate_evolution_report(
        session_public_id="s1", dataset_source_public_id="ds1",
        evolution_analysis={"dataset_status": "Ready", "weak_domains": []}, coverage_report={"by_domain": {}},
        dependency_graph={}, relationship_report={}, expansion_plan=None, version_plan=None,
        knowledge_factory_plan=None, synthetic_dataset_plan=None, quality_evolution=None,
        simulation_report=None, recommendation_report={"recommendation": "wait"},
    )
    assert report["ready_for_admin_review"] is True
    assert report["next_action"] == "wait"


def test_generate_evolution_report_not_ready_without_recommendation() -> None:
    report = generate_evolution_report(
        session_public_id="s1", dataset_source_public_id="ds1",
        evolution_analysis={"dataset_status": "Ready", "weak_domains": []}, coverage_report={"by_domain": {}},
        dependency_graph={}, relationship_report={}, expansion_plan=None, version_plan=None,
        knowledge_factory_plan=None, synthetic_dataset_plan=None, quality_evolution=None,
        simulation_report=None, recommendation_report=None,
    )
    assert report["ready_for_admin_review"] is False
    assert report["next_action"] is None
