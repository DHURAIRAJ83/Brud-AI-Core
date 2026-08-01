"""Phase 19 Step 29 -- deterministic knowledge-gap help FAQ."""

import pytest

from core_model.admin_assistant.knowledge_gap_help import (
    KNOWLEDGE_GAP_FAQ,
    match_knowledge_gap_question,
)

REQUIRED_TOPICS = (
    "what_is_a_knowledge_gap",
    "why_is_a_safety_refusal_not_a_knowledge_gap",
    "what_is_a_capability_gap",
    "why_are_web_and_tool_demand_stored_separately",
    "what_is_a_canonical_question",
    "why_is_raw_user_text_not_stored",
    "how_are_duplicates_clustered",
    "how_is_priority_calculated",
    "why_does_a_resolved_gap_not_enter_training_automatically",
    "what_is_rag_handoff_eligibility",
    "what_is_training_assessment_eligibility",
)


def test_all_eleven_required_topics_are_present() -> None:
    assert set(REQUIRED_TOPICS) == set(KNOWLEDGE_GAP_FAQ.keys())


@pytest.mark.parametrize("key", REQUIRED_TOPICS)
def test_every_entry_has_bilingual_non_empty_answers(key: str) -> None:
    entry = KNOWLEDGE_GAP_FAQ[key]
    assert entry["en"].strip()
    assert entry["ta"].strip()
    assert entry["keywords"]


@pytest.mark.parametrize("key", REQUIRED_TOPICS)
def test_each_entrys_first_keyword_matches_its_own_key(key: str) -> None:
    keyword = KNOWLEDGE_GAP_FAQ[key]["keywords"][0]
    assert match_knowledge_gap_question(keyword) == key


def test_unrelated_message_does_not_match_any_faq() -> None:
    assert match_knowledge_gap_question("what is the weather today") is None


def test_matcher_prefers_longer_more_specific_keyword() -> None:
    # "capability gap" is a substring risk against several entries --
    # confirm the specific one wins.
    assert match_knowledge_gap_question("what is a capability gap") == "what_is_a_capability_gap"
