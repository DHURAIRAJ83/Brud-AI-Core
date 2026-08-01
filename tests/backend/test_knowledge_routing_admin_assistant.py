from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.admin_assistant_tools import ReadOnlyToolError, run_tool, tools_for_mode
from core_model.admin_assistant.dashboard_registry import get_page_by_id, get_page_by_nav_key
from core_model.admin_assistant.intent import classify_intent

_KNOWLEDGE_ROUTING_TOOL_NAMES = (
    "get_knowledge_routing_policy",
    "list_knowledge_routing_reason_codes",
    "get_knowledge_routing_metrics",
    "list_knowledge_routing_decisions",
    "preview_knowledge_routing_classification",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "assistant.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def test_all_five_read_only_tools_are_registered_in_governance_mode() -> None:
    governance_tool_names = {tool.name for tool in tools_for_mode("governance")}
    for name in _KNOWLEDGE_ROUTING_TOOL_NAMES:
        assert name in governance_tool_names


def test_dashboard_page_entry_exists_and_is_marked_implemented() -> None:
    page = get_page_by_id("knowledge_routing")
    assert page is not None
    assert page.implemented is True
    assert page.nav_key == "Knowledge Routing"
    assert "en" in page.title and "ta" in page.title
    assert "en" in page.purpose and "ta" in page.purpose
    assert page.tabs


def test_page_lookup_by_nav_key_matches_sidebar_key() -> None:
    page = get_page_by_nav_key("Knowledge Routing")
    assert page is not None
    assert page.page_id == "knowledge_routing"


def test_no_new_mutating_action_was_registered_for_this_phase() -> None:
    """Phase 17 adds only read-only tools -- it never proposes a
    mutating action, since the classifier has nothing safe to mutate
    beyond its own append-only diagnostic log."""

    from core_model.admin_assistant.action_registry import ACTION_DEFINITIONS

    assert not any("knowledge_routing" in action.action_type for action in ACTION_DEFINITIONS)


def test_get_knowledge_routing_policy_tool(settings: Settings) -> None:
    result = run_tool("get_knowledge_routing_policy", settings, {})
    assert result["available"] is True
    assert result["valid"] is True


def test_list_knowledge_routing_reason_codes_tool(settings: Settings) -> None:
    result = run_tool("list_knowledge_routing_reason_codes", settings, {})
    assert result["count"] > 50


def test_get_knowledge_routing_metrics_tool_on_empty_database(settings: Settings) -> None:
    result = run_tool("get_knowledge_routing_metrics", settings, {})
    assert result["total_classifications"] == 0


def test_preview_tool_requires_text_param(settings: Settings) -> None:
    with pytest.raises(ReadOnlyToolError):
        run_tool("preview_knowledge_routing_classification", settings, {})


def test_preview_tool_never_persists_a_decision(settings: Settings) -> None:
    before = run_tool("get_knowledge_routing_metrics", settings, {})["total_classifications"]
    result = run_tool(
        "preview_knowledge_routing_classification", settings, {"text": "hello there"}
    )
    assert result["recommendation_only"] is True
    assert result["route_executed"] is False
    after = run_tool("get_knowledge_routing_metrics", settings, {})["total_classifications"]
    assert after == before


def test_help_intent_finds_the_knowledge_routing_page() -> None:
    result = classify_intent("help me understand Knowledge Routing")
    assert result.matched_page_id == "knowledge_routing"
    assert result.intent == "help"


def test_navigation_intent_finds_the_knowledge_routing_page() -> None:
    result = classify_intent("take me to Knowledge Routing")
    assert result.matched_page_id == "knowledge_routing"
    assert result.intent == "navigation"
