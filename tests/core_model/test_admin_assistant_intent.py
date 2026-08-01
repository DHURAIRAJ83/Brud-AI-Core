from core_model.admin_assistant.intent import classify_intent


def test_greeting_english() -> None:
    result = classify_intent("Hello")
    assert result.intent == "greeting"


def test_greeting_tamil() -> None:
    result = classify_intent("வணக்கம்")
    assert result.intent == "greeting"


def test_help_matches_page_name() -> None:
    result = classify_intent("How do I use the Datasets page?")
    assert result.intent == "help"
    assert result.matched_page_id == "datasets"


def test_pending_work_intent() -> None:
    result = classify_intent("What is pending right now?")
    assert result.intent == "pending_work"


def test_pending_work_tamil() -> None:
    result = classify_intent("நிலுவையில் என்ன இருக்கு?")
    assert result.intent == "pending_work"


def test_navigation_intent_requires_page_match() -> None:
    result = classify_intent("take me to Builds & Pipelines")
    assert result.intent == "navigation"
    assert result.matched_page_id == "builds_pipelines"


def test_navigation_words_without_page_match_falls_back() -> None:
    result = classify_intent("go somewhere random")
    assert result.intent != "navigation"


def test_open_ended_when_nothing_matches() -> None:
    result = classify_intent("Why did the last evaluation run score lower than expected?")
    assert result.intent == "open_ended"


def test_help_intent_when_page_mentioned_without_help_words() -> None:
    result = classify_intent("Corpus Builder")
    assert result.intent == "help"
    assert result.matched_page_id == "corpus_builder"


def test_help_matches_production_readiness_page() -> None:
    # Regression test for a real gap found by Phase 15A's final canonical
    # regression run: "Production Readiness" was missing from
    # DASHBOARD_PAGES entirely, so the assistant could not recognize or
    # explain this page at all until it was registered.
    result = classify_intent("How do I use the Production Readiness page?")
    assert result.intent == "help"
    assert result.matched_page_id == "production_readiness"
