"""MB-10: pure-module unit tests for
core_model/mini_brain/research_center/."""

from core_model.mini_brain.research_center.citation_analyzer import analyze_citations
from core_model.mini_brain.research_center.conflict_resolver import resolve_conflicts
from core_model.mini_brain.research_center.dataset_draft_builder import build_dataset_draft
from core_model.mini_brain.research_center.duplicate_resolver import resolve_duplicates
from core_model.mini_brain.research_center.evidence_validator import validate_evidence
from core_model.mini_brain.research_center.provider_consensus_engine import build_consensus
from core_model.mini_brain.research_center.provider_registry import (
    DEFAULT_PROVIDER_KEYS,
    select_providers,
)
from core_model.mini_brain.research_center.research_quality_engine import (
    score_overall,
    score_provider,
)
from core_model.mini_brain.research_center.research_recommendation_engine import (
    GOOD_QUALITY_THRESHOLD,
    LOW_QUALITY_THRESHOLD,
    recommend_next_step,
)
from core_model.mini_brain.research_center.research_report_generator import (
    generate_research_report,
)
from core_model.mini_brain.research_center.research_request_builder import build_research_request

# -- research_request_builder -----------------------------------------------------


def test_build_research_request_produces_three_questions() -> None:
    result = build_research_request(topic="Photosynthesis", evidence={"case_count": 2})
    assert len(result["questions"]) == 3
    assert all("Photosynthesis" in q for q in result["questions"])
    assert result["status"] == "prepared"
    assert result["priority"] is None


def test_build_research_request_carries_evidence_and_priority_through_unchanged() -> None:
    evidence = {"roadmap": {"weak_domains": ["History"]}}
    result = build_research_request(topic="History", evidence=evidence, priority="high")
    assert result["evidence"] is evidence
    assert result["priority"] == "high"


# -- provider_registry --------------------------------------------------------------


def _provider(key: str, status: str = "active") -> dict:
    return {"provider_key": key, "display_name": key.title(), "status": status}


def test_select_providers_all_active_and_known() -> None:
    registered = [_provider("claude"), _provider("openai")]
    result = select_providers(requested_provider_keys=["claude", "openai"], registered_providers=registered)
    assert result["valid"] is True
    assert [p["provider_key"] for p in result["selected_providers"]] == ["claude", "openai"]
    assert result["unknown_provider_keys"] == []


def test_select_providers_rejects_unknown_key() -> None:
    registered = [_provider("claude")]
    result = select_providers(requested_provider_keys=["claude", "bogus"], registered_providers=registered)
    assert result["valid"] is False
    assert result["unknown_provider_keys"] == ["bogus"]
    assert len(result["selected_providers"]) == 1


def test_select_providers_treats_inactive_as_unknown() -> None:
    registered = [_provider("claude", status="inactive")]
    result = select_providers(requested_provider_keys=["claude"], registered_providers=registered)
    assert result["valid"] is False
    assert result["unknown_provider_keys"] == ["claude"]


def test_select_providers_empty_request_is_invalid() -> None:
    result = select_providers(requested_provider_keys=[], registered_providers=[_provider("claude")])
    assert result["valid"] is False
    assert result["selected_providers"] == []


def test_default_provider_keys_matches_five_seeded_defaults() -> None:
    assert DEFAULT_PROVIDER_KEYS == ("claude", "openai", "gemini", "openrouter", "local_model")


# -- citation_analyzer --------------------------------------------------------------


def test_analyze_citations_detects_all_marker_types() -> None:
    text = "According to a study (2020) [1], see https://example.com for details."
    result = analyze_citations(text=text)
    assert result["url_count"] == 1
    assert result["year_reference_count"] == 1
    assert result["numbered_reference_count"] == 1
    assert result["attribution_phrase_count"] == 1
    assert result["total_citation_markers"] == 4
    assert result["has_any_citation"] is True


def test_analyze_citations_no_markers() -> None:
    result = analyze_citations(text="This is a plain statement with no sourcing at all.")
    assert result["total_citation_markers"] == 0
    assert result["citation_score"] == 0.0
    assert result["has_any_citation"] is False


def test_analyze_citations_score_caps_at_100() -> None:
    text = "According to source: cited from reported by per the [1][2][3][4][5][6] (2020) (2021)"
    result = analyze_citations(text=text)
    assert result["citation_score"] == 100.0


# -- evidence_validator ---------------------------------------------------------------


def test_validate_evidence_flags_unsupported_absolute_claims() -> None:
    text = "This is always definitely true with no exception whatsoever in every single documented case ever recorded anywhere in history."
    result = validate_evidence(text=text, citation_marker_count=0)
    assert result["unsupported_claims"] is True
    assert result["evidence_score"] < 100.0


def test_validate_evidence_absolute_claim_with_citation_is_not_unsupported() -> None:
    text = "This is always true according to the cited historical record spanning many independently documented decades of research."
    result = validate_evidence(text=text, citation_marker_count=1)
    assert result["unsupported_claims"] is False


def test_validate_evidence_flags_weak_hedging() -> None:
    text = "It might be true, and perhaps it could possibly be unclear whether this holds in every documented scenario across time."
    result = validate_evidence(text=text, citation_marker_count=0)
    assert result["weak_evidence"] is True


def test_validate_evidence_flags_missing_facts_below_word_bound() -> None:
    result = validate_evidence(text="Too short.", citation_marker_count=0)
    assert result["missing_facts"] is True
    assert result["word_count"] == 2


def test_validate_evidence_perfect_text_scores_100() -> None:
    text = (
        "Photosynthesis is the process by which green plants, algae, and some bacteria convert light "
        "energy into chemical energy stored in glucose molecules, releasing oxygen as a byproduct of "
        "the reaction that occurs in chloroplasts."
    )
    result = validate_evidence(text=text, citation_marker_count=0)
    assert result["unsupported_claims"] is False
    assert result["weak_evidence"] is False
    assert result["missing_facts"] is False
    assert result["evidence_score"] == 100.0


def test_validate_evidence_score_floors_at_zero() -> None:
    text = "always never definitely certainly might may possibly perhaps unclear i think it seems short"
    result = validate_evidence(text=text, citation_marker_count=0)
    assert result["evidence_score"] == 0.0


# -- duplicate_resolver ---------------------------------------------------------------


def test_resolve_duplicates_no_groups_scores_100() -> None:
    result = resolve_duplicates(duplicate_groups=[], provider_count=3)
    assert result["duplicate_group_count"] == 0
    assert result["duplicate_score"] == 100.0
    assert result["independent_signal_count"] == 3


def test_resolve_duplicates_penalizes_by_duplicated_provider_count() -> None:
    result = resolve_duplicates(duplicate_groups=[["claude", "openai"]], provider_count=3)
    assert result["duplicate_group_count"] == 1
    assert result["duplicated_provider_count"] == 2
    assert result["duplicate_score"] == 70.0
    assert result["independent_signal_count"] == 2  # (3 - 2) + 1 group


def test_resolve_duplicates_score_never_negative() -> None:
    groups = [[f"p{i}", f"p{i}b"] for i in range(10)]
    result = resolve_duplicates(duplicate_groups=groups, provider_count=20)
    assert result["duplicate_score"] == 0.0


# -- conflict_resolver ----------------------------------------------------------------


def test_resolve_conflicts_no_conflicts_scores_100() -> None:
    result = resolve_conflicts(conflict_groups=[], provider_count=3)
    assert result["conflict_count"] == 0
    assert result["conflict_score"] == 100.0
    assert result["has_unresolved_conflicts"] is False


def test_resolve_conflicts_binary_split_with_three_plus_providers_suggests_majority() -> None:
    groups = [{"key": "topic", "conflicting_values": ["A", "B"]}]
    result = resolve_conflicts(conflict_groups=groups, provider_count=3)
    assert "majority_available" in result["resolutions"][0]["recommendation"]
    assert result["has_unresolved_conflicts"] is True


def test_resolve_conflicts_two_providers_has_no_majority() -> None:
    groups = [{"key": "topic", "conflicting_values": ["A", "B"]}]
    result = resolve_conflicts(conflict_groups=groups, provider_count=2)
    assert "no_majority" in result["resolutions"][0]["recommendation"]


def test_resolve_conflicts_score_floors_at_zero() -> None:
    groups = [{"key": f"k{i}", "conflicting_values": ["A", "B"]} for i in range(6)]
    result = resolve_conflicts(conflict_groups=groups, provider_count=2)
    assert result["conflict_score"] == 0.0


# -- provider_consensus_engine ---------------------------------------------------------


def _outputs(*providers: str) -> list[dict]:
    return [{"provider": p, "output_text": f"{p} says something."} for p in providers]


def test_build_consensus_no_providers() -> None:
    result = build_consensus(
        provider_outputs=[],
        duplicate_resolution=resolve_duplicates(duplicate_groups=[], provider_count=0),
        conflict_resolution=resolve_conflicts(conflict_groups=[], provider_count=0),
    )
    assert result["verdict"] == "no_data"
    assert result["agreement_score"] == 0.0


def test_build_consensus_conflicting_takes_priority() -> None:
    outputs = _outputs("claude", "openai")
    dup = resolve_duplicates(duplicate_groups=[], provider_count=2)
    conf = resolve_conflicts(conflict_groups=[{"key": "k", "conflicting_values": ["A", "B"]}], provider_count=2)
    result = build_consensus(provider_outputs=outputs, duplicate_resolution=dup, conflict_resolution=conf)
    assert result["verdict"] == "conflicting"
    assert result["agreement_score"] == 30.0


def test_build_consensus_strong_agreement_when_duplicates_and_no_conflicts() -> None:
    outputs = _outputs("claude", "openai", "gemini")
    dup = resolve_duplicates(duplicate_groups=[["claude", "openai"]], provider_count=3)
    conf = resolve_conflicts(conflict_groups=[], provider_count=3)
    result = build_consensus(provider_outputs=outputs, duplicate_resolution=dup, conflict_resolution=conf)
    assert result["verdict"] == "strong_agreement"
    assert result["agreement_score"] == 90.0


def test_build_consensus_partial_agreement_multi_provider_no_duplicates_no_conflicts() -> None:
    outputs = _outputs("claude", "openai")
    dup = resolve_duplicates(duplicate_groups=[], provider_count=2)
    conf = resolve_conflicts(conflict_groups=[], provider_count=2)
    result = build_consensus(provider_outputs=outputs, duplicate_resolution=dup, conflict_resolution=conf)
    assert result["verdict"] == "partial_agreement"
    assert result["agreement_score"] == 60.0


def test_build_consensus_single_source() -> None:
    outputs = _outputs("claude")
    dup = resolve_duplicates(duplicate_groups=[], provider_count=1)
    conf = resolve_conflicts(conflict_groups=[], provider_count=1)
    result = build_consensus(provider_outputs=outputs, duplicate_resolution=dup, conflict_resolution=conf)
    assert result["verdict"] == "single_source"
    assert result["agreement_score"] == 40.0


def test_build_consensus_traceable_outputs_preserve_every_provider() -> None:
    outputs = _outputs("claude", "openai")
    dup = resolve_duplicates(duplicate_groups=[], provider_count=2)
    conf = resolve_conflicts(conflict_groups=[], provider_count=2)
    result = build_consensus(provider_outputs=outputs, duplicate_resolution=dup, conflict_resolution=conf)
    assert [t["provider"] for t in result["traceable_outputs"]] == ["claude", "openai"]


# -- research_quality_engine -----------------------------------------------------------


def test_score_provider_complete_evidence_scores_100_completeness() -> None:
    evidence = {"evidence_score": 100.0, "missing_facts": False}
    citation = {"citation_score": 60.0}
    result = score_provider(provider="claude", evidence_result=evidence, citation_result=citation)
    assert result["completeness_score"] == 100.0
    assert result["trust_score"] == round((100.0 + 60.0 + 100.0) / 3, 1)


def test_score_provider_missing_facts_scores_40_completeness() -> None:
    evidence = {"evidence_score": 70.0, "missing_facts": True}
    citation = {"citation_score": 0.0}
    result = score_provider(provider="claude", evidence_result=evidence, citation_result=citation)
    assert result["completeness_score"] == 40.0


def test_score_overall_averages_provider_scores_and_aggregate_signals() -> None:
    provider_scores = [
        {"evidence_score": 80.0, "citation_score": 60.0, "completeness_score": 100.0, "trust_score": 80.0},
        {"evidence_score": 60.0, "citation_score": 40.0, "completeness_score": 40.0, "trust_score": 46.7},
    ]
    result = score_overall(
        provider_scores=provider_scores, agreement_score=90.0, conflict_score=100.0, duplicate_score=100.0,
    )
    assert result["evidence_score"] == 70.0
    assert result["citation_score"] == 50.0
    assert result["completeness_score"] == 70.0
    assert result["per_provider"] == provider_scores
    expected_overall = round(sum([70.0, 90.0, 100.0, 100.0, 50.0, 70.0, result["trust_score"]]) / 7, 1)
    assert result["overall_quality"] == expected_overall


def test_score_overall_no_providers_defaults_to_zero_provider_signals() -> None:
    result = score_overall(provider_scores=[], agreement_score=0.0, conflict_score=100.0, duplicate_score=100.0)
    assert result["evidence_score"] == 0.0
    assert result["citation_score"] == 0.0
    assert result["completeness_score"] == 0.0
    assert result["trust_score"] == 0.0


# -- dataset_draft_builder --------------------------------------------------------------


def test_build_dataset_draft_is_never_verified() -> None:
    draft = build_dataset_draft(topic="Cell Biology", mode="local_draft")
    assert draft["verified"] is False
    assert draft["status"] == "needs_admin_review"
    assert draft["required_topics"] == ["Cell Biology"]
    assert len(draft["structure"]) == 4
    assert all("Cell Biology" in section for section in draft["structure"])
    assert draft["sources"] == []


def test_build_dataset_draft_carries_quality_and_sources_through() -> None:
    quality = {"overall_quality": 72.0}
    sources = [{"provider": "claude", "output_text": "x"}]
    draft = build_dataset_draft(topic="Quantum", mode="multi_provider", quality_report=quality, traceable_sources=sources)
    assert draft["quality_summary"] is quality
    assert draft["sources"] is sources


# -- research_recommendation_engine ------------------------------------------------------


def test_recommend_next_step_zero_providers_suggests_local_draft() -> None:
    result = recommend_next_step(overall_quality=0.0, has_unresolved_conflicts=False, provider_count=0)
    assert result["recommendation"] == "request_local_draft"


def test_recommend_next_step_conflicts_and_low_quality_suggests_different_providers() -> None:
    result = recommend_next_step(
        overall_quality=LOW_QUALITY_THRESHOLD - 1, has_unresolved_conflicts=True, provider_count=2,
    )
    assert result["recommendation"] == "request_different_providers"


def test_recommend_next_step_low_quality_without_conflicts_suggests_more_research() -> None:
    result = recommend_next_step(
        overall_quality=LOW_QUALITY_THRESHOLD - 1, has_unresolved_conflicts=False, provider_count=2,
    )
    assert result["recommendation"] == "request_more_research"


def test_recommend_next_step_high_quality_suggests_accept_draft() -> None:
    result = recommend_next_step(
        overall_quality=GOOD_QUALITY_THRESHOLD, has_unresolved_conflicts=False, provider_count=2,
    )
    assert result["recommendation"] == "accept_draft"


def test_recommend_next_step_moderate_quality_suggests_edit() -> None:
    midpoint = (LOW_QUALITY_THRESHOLD + GOOD_QUALITY_THRESHOLD) / 2
    result = recommend_next_step(overall_quality=midpoint, has_unresolved_conflicts=False, provider_count=2)
    assert result["recommendation"] == "edit"


# -- research_report_generator -----------------------------------------------------------


def test_generate_research_report_ready_when_draft_present() -> None:
    report = generate_research_report(
        session_public_id="s1", research_request={"topic": "X"}, mode="local_draft",
        selected_providers=[], consensus_report=None, quality_report=None,
        dataset_draft={"status": "needs_admin_review"}, recommendation=None,
    )
    assert report["ready_for_admin_review"] is True
    assert report["session_public_id"] == "s1"


def test_generate_research_report_not_ready_without_draft() -> None:
    report = generate_research_report(
        session_public_id="s1", research_request={"topic": "X"}, mode=None,
        selected_providers=[], consensus_report=None, quality_report=None,
        dataset_draft=None, recommendation=None,
    )
    assert report["ready_for_admin_review"] is False
    assert report["rag_report"] is None
