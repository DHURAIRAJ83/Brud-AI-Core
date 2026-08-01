"""Phase 20 Step 33 -- deterministic Trusted Web / deterministic-tool help FAQ."""

import pytest

from core_model.admin_assistant.trusted_web_help import (
    TRUSTED_WEB_FAQ,
    match_trusted_web_question,
)

REQUIRED_TOPICS = (
    "what_is_trusted_web_search",
    "how_is_a_source_verified",
    "why_are_some_search_results_rejected",
    "what_is_freshness",
    "what_happens_when_sources_conflict",
    "why_no_current_facts_from_model_memory",
    "what_is_a_deterministic_tool",
    "why_is_calculator_output_authoritative",
    "what_is_mcp",
    "why_is_external_mcp_disabled",
    "why_only_three_public_tools",
)


def test_all_eleven_required_topics_are_present() -> None:
    assert set(REQUIRED_TOPICS) == set(TRUSTED_WEB_FAQ.keys())


@pytest.mark.parametrize("key", REQUIRED_TOPICS)
def test_every_entry_has_bilingual_non_empty_answers(key: str) -> None:
    entry = TRUSTED_WEB_FAQ[key]
    assert entry["en"].strip()
    assert entry["ta"].strip()
    assert entry["keywords"]


@pytest.mark.parametrize("key", REQUIRED_TOPICS)
def test_each_entrys_first_keyword_matches_its_own_key(key: str) -> None:
    keyword = TRUSTED_WEB_FAQ[key]["keywords"][0]
    assert match_trusted_web_question(keyword) == key


def test_unmatched_message_returns_none() -> None:
    assert match_trusted_web_question("completely unrelated question about datasets") is None


def test_longest_keyword_wins_over_a_shorter_substring() -> None:
    # "what is mcp" is a substring-adjacent phrase to nothing else here,
    # but the matcher must still pick the longest matching keyword overall.
    result = match_trusted_web_question("why is external mcp disabled in this system")
    assert result == "why_is_external_mcp_disabled"
