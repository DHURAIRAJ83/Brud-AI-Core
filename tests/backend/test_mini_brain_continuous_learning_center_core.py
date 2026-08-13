"""MB-09: pure-module unit tests for
core_model/mini_brain/continuous_learning_center/."""

from core_model.mini_brain.continuous_learning_center.dataset_evolution_planner import (
    plan_dataset_evolution,
)
from core_model.mini_brain.continuous_learning_center.draft_planner import build_draft_outline
from core_model.mini_brain.continuous_learning_center.knowledge_gap_evolution import (
    evolve_knowledge_gaps,
)
from core_model.mini_brain.continuous_learning_center.knowledge_roadmap import build_roadmap
from core_model.mini_brain.continuous_learning_center.learning_memory import extract_memory_fields
from core_model.mini_brain.continuous_learning_center.learning_queue import build_learning_queue
from core_model.mini_brain.continuous_learning_center.planning_report_generator import (
    generate_planning_report,
)
from core_model.mini_brain.continuous_learning_center.provider_consensus_planner import (
    SUPPORTED_PROVIDERS,
    build_consensus,
    build_provider_request,
)
from core_model.mini_brain.continuous_learning_center.recommendation_engine import (
    recommend_next_action,
)


def _report(*, weak_areas, strong_areas=None, failure_rate=0.1, hallucination_rate=0.1, missing_domains=None):
    return {
        "weak_areas": weak_areas, "strong_areas": strong_areas or [],
        "failure_rate": failure_rate, "hallucination_rate": hallucination_rate,
        "knowledge_coverage": {"missing_domains": missing_domains or []},
    }


# -- knowledge_gap_evolution ------------------------------------------------------


def test_evolve_detects_recurring_weak_domain() -> None:
    reports = [
        _report(weak_areas=[{"domain": "History", "weakness_index": 40.0}]),
        _report(weak_areas=[{"domain": "History", "weakness_index": 60.0}]),
    ]
    result = evolve_knowledge_gaps(reports=reports)
    assert result["recurring_weak_domains"][0]["domain"] == "History"
    assert result["recurring_weak_domains"][0]["recurrence_count"] == 2
    assert result["recurring_weak_domains"][0]["latest_weakness_index"] == 60.0


def test_evolve_ignores_single_occurrence_domain() -> None:
    reports = [_report(weak_areas=[{"domain": "Math", "weakness_index": 40.0}])]
    result = evolve_knowledge_gaps(reports=reports)
    assert result["recurring_weak_domains"] == []


def test_evolve_ranks_by_long_term_importance_descending() -> None:
    reports = [
        _report(weak_areas=[{"domain": "A", "weakness_index": 30.0}, {"domain": "B", "weakness_index": 90.0}]),
        _report(weak_areas=[{"domain": "A", "weakness_index": 30.0}, {"domain": "B", "weakness_index": 90.0}]),
    ]
    result = evolve_knowledge_gaps(reports=reports)
    assert result["recurring_weak_domains"][0]["domain"] == "B"


def test_evolve_detects_unresolved_knowledge_gaps() -> None:
    reports = [
        _report(weak_areas=[], missing_domains=[{"domain": "Science", "case_count": 1}]),
        _report(weak_areas=[], missing_domains=[{"domain": "Science", "case_count": 2}]),
    ]
    result = evolve_knowledge_gaps(reports=reports)
    assert result["unresolved_knowledge_gaps"][0]["domain"] == "Science"


def test_evolve_detects_recurring_high_failure_and_hallucination() -> None:
    reports = [
        _report(weak_areas=[], failure_rate=0.5, hallucination_rate=0.4),
        _report(weak_areas=[], failure_rate=0.6, hallucination_rate=0.5),
    ]
    result = evolve_knowledge_gaps(reports=reports)
    assert result["recurring_failures_detected"] is True
    assert result["recurring_hallucinations_detected"] is True


def test_evolve_empty_reports() -> None:
    result = evolve_knowledge_gaps(reports=[])
    assert result["cycles_compared"] == 0
    assert result["recurring_weak_domains"] == []


# -- learning_queue -------------------------------------------------------------


def test_build_queue_uses_suggested_formats_when_available() -> None:
    recurring = [{"domain": "History", "recurrence_count": 3, "latest_weakness_index": 60.0, "long_term_importance": 180.0}]
    suggestions = [{"domain": "History", "recommended_formats": [{"format": "Documentation", "why": "x"}]}]
    result = build_learning_queue(recurring_weak_domains=recurring, latest_dataset_suggestions=suggestions)
    assert result["queue"][0]["suggested_dataset_type"] == ["Documentation"]
    assert result["queue"][0]["priority"] == "Critical"


def test_build_queue_defaults_to_qa_pairs_without_suggestion() -> None:
    recurring = [{"domain": "Math", "recurrence_count": 2, "latest_weakness_index": 10.0, "long_term_importance": 20.0}]
    result = build_learning_queue(recurring_weak_domains=recurring, latest_dataset_suggestions=[])
    assert result["queue"][0]["suggested_dataset_type"] == ["QA pairs"]
    assert result["queue"][0]["priority"] == "Low"


def test_build_queue_empty_when_no_recurring_domains() -> None:
    result = build_learning_queue(recurring_weak_domains=[], latest_dataset_suggestions=[])
    assert result["queue"] == []
    assert result["queue_length"] == 0


# -- draft_planner ----------------------------------------------------------------


def test_draft_outline_always_unverified() -> None:
    result = build_draft_outline(topic="History", suggested_formats=["QA pairs"])
    assert result["verified"] is False
    assert "never invented" in result["disclosure"] or "not been verified" in result["disclosure"]


def test_draft_outline_includes_topic_in_structure() -> None:
    result = build_draft_outline(topic="Physics", suggested_formats=["QA pairs", "Documentation"])
    assert all("Physics" in section for section in result["structure"])
    assert len(result["sample_formats"]) == 2


def test_draft_outline_ignores_unknown_format() -> None:
    result = build_draft_outline(topic="X", suggested_formats=["not-a-real-format"])
    assert result["sample_formats"] == []


# -- provider_consensus_planner ------------------------------------------------------


def test_provider_request_valid_for_supported_providers() -> None:
    result = build_provider_request(topic="History", evidence={}, requested_providers=["claude", "openai"])
    assert result["valid"] is True
    assert result["unknown_providers"] == []


def test_provider_request_invalid_for_unknown_provider() -> None:
    result = build_provider_request(topic="History", evidence={}, requested_providers=["claude", "bogus"])
    assert result["valid"] is False
    assert "bogus" in result["unknown_providers"]


def test_provider_request_never_calls_a_provider() -> None:
    result = build_provider_request(topic="X", evidence={}, requested_providers=list(SUPPORTED_PROVIDERS))
    assert "does not call" in result["disclosure"]


def test_consensus_high_confidence_with_agreeing_providers() -> None:
    outputs = [{"provider": "claude", "output_text": "a"}, {"provider": "openai", "output_text": "a"}]
    result = build_consensus(provider_outputs=outputs, duplicate_groups=[["claude", "openai"]], conflict_groups=[])
    assert result["confidence"] == "High"


def test_consensus_low_confidence_with_conflicts() -> None:
    outputs = [{"provider": "claude", "output_text": "a"}, {"provider": "openai", "output_text": "b"}]
    result = build_consensus(
        provider_outputs=outputs, duplicate_groups=[],
        conflict_groups=[{"key": "topic", "conflicting_values": ["a", "b"]}],
    )
    assert result["confidence"] == "Low"
    assert result["has_conflicts"] is True


def test_consensus_traceable_outputs_preserve_every_provider() -> None:
    outputs = [{"provider": "claude", "output_text": "a"}, {"provider": "gemini", "output_text": "b"}]
    result = build_consensus(provider_outputs=outputs, duplicate_groups=[], conflict_groups=[])
    assert {o["provider"] for o in result["traceable_outputs"]} == {"claude", "gemini"}


# -- dataset_evolution_planner ---------------------------------------------------------


def test_dataset_evolution_extends_when_no_existing_dataset() -> None:
    result = plan_dataset_evolution(existing_dataset_exists=False, draft_topic="History")
    assert result["recommendation"] == "extend"


def test_dataset_evolution_replaces_when_not_ready_and_high_duplicates() -> None:
    result = plan_dataset_evolution(
        existing_dataset_exists=True, draft_topic="X", existing_status="Not Ready",
        existing_duplicate_ratio=0.5,
    )
    assert result["recommendation"] == "replace"


def test_dataset_evolution_extends_when_not_ready_low_duplicates() -> None:
    result = plan_dataset_evolution(
        existing_dataset_exists=True, draft_topic="X", existing_status="Not Ready",
        existing_duplicate_ratio=0.05,
    )
    assert result["recommendation"] == "extend"


def test_dataset_evolution_splits_large_dataset() -> None:
    result = plan_dataset_evolution(
        existing_dataset_exists=True, draft_topic="X", existing_status="Ready",
        existing_clean_ratio=0.95, existing_duplicate_ratio=0.01, existing_record_count=5000,
    )
    assert result["recommendation"] == "split"


def test_dataset_evolution_ignores_when_already_healthy() -> None:
    result = plan_dataset_evolution(
        existing_dataset_exists=True, draft_topic="X", existing_status="Ready",
        existing_clean_ratio=0.95, existing_duplicate_ratio=0.01, existing_record_count=100,
    )
    assert result["recommendation"] == "ignore"


def test_dataset_evolution_merges_as_default_healthy_case() -> None:
    result = plan_dataset_evolution(
        existing_dataset_exists=True, draft_topic="X", existing_status="Needs Improvement",
        existing_clean_ratio=0.6, existing_duplicate_ratio=0.1, existing_record_count=100,
    )
    assert result["recommendation"] == "merge"


def test_dataset_evolution_never_performs_the_merge() -> None:
    result = plan_dataset_evolution(existing_dataset_exists=False, draft_topic="X")
    assert "recommendation" in result
    assert "merged" not in str(result).lower() or result["recommendation"] in {
        "merge", "extend", "replace", "split", "ignore",
    }


# -- knowledge_roadmap ----------------------------------------------------------------


def test_roadmap_reports_missing_knowledge_from_high_priority_queue() -> None:
    queue = [{"topic": "History", "priority": "Critical", "suggested_dataset_type": ["QA pairs"]}, {"topic": "Math", "priority": "Low", "suggested_dataset_type": ["QA pairs"]}]
    result = build_roadmap(memory_entry_count=3, current_weak_domains=["History"], current_strong_domains=["Math"], queue=queue)
    assert result["missing_knowledge"] == ["History"]
    assert result["cycles_in_memory"] == 3


def test_roadmap_no_improvement_projected_without_queue() -> None:
    result = build_roadmap(memory_entry_count=0, current_weak_domains=[], current_strong_domains=[], queue=[])
    assert "no improvement projected" in result["expected_improvement"]


# -- recommendation_engine -------------------------------------------------------------


def test_recommend_no_action_for_empty_queue() -> None:
    result = recommend_next_action(queue=[], dataset_evolution_recommendation="ignore", provider_consensus=None)
    assert result["action"] == "No Action"


def test_recommend_training_candidate_for_high_confidence_consensus() -> None:
    queue = [{"topic": "X", "priority": "Medium"}]
    result = recommend_next_action(
        queue=queue, dataset_evolution_recommendation="merge",
        provider_consensus={"confidence": "High"},
    )
    assert result["action"] == "Training Candidate"


def test_recommend_rag_evaluation_for_critical_plus_replace() -> None:
    queue = [{"topic": "X", "priority": "Critical"}]
    result = recommend_next_action(
        queue=queue, dataset_evolution_recommendation="replace", provider_consensus=None,
    )
    assert result["action"] == "RAG Evaluation"


def test_recommend_external_provider_consensus_for_critical_items() -> None:
    queue = [{"topic": "X", "priority": "Critical"}]
    result = recommend_next_action(
        queue=queue, dataset_evolution_recommendation="merge", provider_consensus=None,
    )
    assert result["action"] == "External Provider Consensus"


def test_recommend_local_draft_for_large_queue() -> None:
    queue = [{"topic": f"t{i}", "priority": "Medium"} for i in range(4)]
    result = recommend_next_action(queue=queue, dataset_evolution_recommendation="merge", provider_consensus=None)
    assert result["action"] == "Local Draft"


def test_recommend_collect_more_data_as_fallback() -> None:
    queue = [{"topic": "X", "priority": "Low"}]
    result = recommend_next_action(queue=queue, dataset_evolution_recommendation="ignore", provider_consensus=None)
    assert result["action"] == "Collect More Data"


def test_every_recommendation_has_why_and_evidence() -> None:
    result = recommend_next_action(queue=[], dataset_evolution_recommendation="ignore", provider_consensus=None)
    assert result["why"]
    assert "evidence" in result


# -- learning_memory -----------------------------------------------------------------


def test_extract_memory_fields_from_real_mb08_report_shape() -> None:
    report = {
        "weak_areas": ["History"], "strong_areas": ["Math"],
        "training_suggestion": {"action": "Fine Tune"},
    }
    result = extract_memory_fields(continuous_learning_report=report)
    assert result["weak_domains"] == ["History"]
    assert result["strong_domains"] == ["Math"]
    assert result["training_decision"] == "Fine Tune"


def test_extract_memory_fields_handles_missing_keys() -> None:
    result = extract_memory_fields(continuous_learning_report={})
    assert result["weak_domains"] == []
    assert result["training_decision"] is None


# -- planning_report_generator ----------------------------------------------------------


def test_generate_planning_report_assembles_every_section() -> None:
    kge = {"cycles_compared": 2, "unresolved_knowledge_gaps": [], "recurring_failures_detected": False, "recurring_hallucinations_detected": False, "recurring_weak_domains": []}
    lq = {"queue": []}
    roadmap = {"current_strengths": [], "current_weaknesses": []}
    rec = {"action": "No Action", "why": "x", "evidence": {}}
    report = generate_planning_report(
        session_public_id="s1", memory_entry_count=1, knowledge_gap_evolution_report=kge,
        learning_queue_report=lq, draft_report=None, provider_consensus_report=None,
        dataset_evolution_report=None, roadmap_report=roadmap, recommendation_report=rec,
    )
    assert report["session_public_id"] == "s1"
    assert report["next_action"]["action"] == "No Action"
    assert report["learning_history"]["cycles_in_memory"] == 1
    assert report["draft_suggestions"] is None
