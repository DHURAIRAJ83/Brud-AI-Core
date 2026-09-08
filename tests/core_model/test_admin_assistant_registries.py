import json
from pathlib import Path

from core_model.admin_assistant.action_registry import (
    ACTION_DEFINITIONS,
    RISK_LEVELS,
    actions_for_mode,
    actions_for_risk_level,
    get_action_definition,
    is_blocked_action_type,
    is_known_action_type,
)
from core_model.admin_assistant.dashboard_registry import (
    ASSISTANT_MODES,
    DASHBOARD_PAGES,
    DOCUMENT_NAVIGATION_TARGETS,
    NAVIGATION_TARGET_BY_KEY,
    get_page_by_id,
    get_page_by_nav_key,
    pages_for_mode,
    resolve_document_navigation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SIDEBAR_PATH = REPO_ROOT / "apps/admin-dashboard/src/components/Sidebar.jsx"
DOCUMENTS_PAGE_PATH = REPO_ROOT / "apps/admin-dashboard/src/pages/DocumentsPage.jsx"
DOCUMENT_NAVIGATION_JS_PATH = (
    REPO_ROOT / "apps/admin-dashboard/src/services/documentNavigation.js"
)


def _real_nav_keys() -> set[str]:
    source = SIDEBAR_PATH.read_text(encoding="utf-8")
    keys = set()
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("{ key:") and "label:" in stripped:
            key = stripped.split("key:", 1)[1].split(",", 1)[0].strip().strip("'\"")
            keys.add(key)
    return keys


def _real_documents_page_tabs() -> list[str]:
    source = DOCUMENTS_PAGE_PATH.read_text(encoding="utf-8")
    marker = "const tabs = ["
    start = source.index(marker) + len(marker)
    end = source.index("]", start)
    body = source[start:end]
    return [item.strip().strip("'\"") for item in body.split(",") if item.strip()]


def _frontend_document_nav_targets() -> dict[str, dict[str, object]]:
    """Regex-parses DOCUMENT_NAV_TARGETS out of documentNavigation.js -- the
    same technique `_real_nav_keys()` already uses against Sidebar.jsx --
    so the JS and Python registries can never silently drift apart."""

    source = DOCUMENT_NAVIGATION_JS_PATH.read_text(encoding="utf-8")
    start = source.index("export const DOCUMENT_NAV_TARGETS = {")
    start = source.index("{", start)
    end = source.index("\n}", start)
    body = source[start + 1 : end]
    targets: dict[str, dict[str, object]] = {}
    for line in body.splitlines():
        stripped = line.strip().rstrip(",")
        if not stripped.startswith("'"):
            continue
        key = stripped.split("'", 2)[1]
        nav_key_match = stripped.split("navKey:", 1)[1].split("'", 2)[1]
        entry: dict[str, object] = {"navKey": nav_key_match}
        if "documentsTab:" in stripped:
            entry["documentsTab"] = stripped.split("documentsTab:", 1)[1].split("'", 2)[1]
        if "wizardStep:" in stripped:
            step_part = stripped.split("wizardStep:", 1)[1].split("}", 1)[0]
            entry["wizardStep"] = int("".join(ch for ch in step_part if ch.isdigit()))
        targets[key] = entry
    return targets


def test_every_real_nav_key_is_registered() -> None:
    real_keys = _real_nav_keys()
    implemented_keys = {page.nav_key for page in DASHBOARD_PAGES if page.implemented}
    assert real_keys == implemented_keys


def test_page_ids_and_nav_keys_are_unique() -> None:
    ids = [page.page_id for page in DASHBOARD_PAGES]
    nav_keys = [page.nav_key for page in DASHBOARD_PAGES]
    assert len(ids) == len(set(ids))
    assert len(nav_keys) == len(set(nav_keys))


def test_every_page_has_a_valid_mode() -> None:
    for page in DASHBOARD_PAGES:
        assert page.mode in ASSISTANT_MODES


def test_placeholder_pages_are_marked_not_implemented() -> None:
    for key in ("Chat Testing", "Audit Logs", "Settings"):
        page = get_page_by_nav_key(key)
        assert page is not None
        assert page.implemented is False


def test_related_page_ids_reference_real_pages() -> None:
    known_ids = {page.page_id for page in DASHBOARD_PAGES}
    for page in DASHBOARD_PAGES:
        for related in page.related_page_ids:
            assert related in known_ids, f"{page.page_id} references unknown page {related}"


def test_lookup_helpers() -> None:
    assert get_page_by_id("datasets") is not None
    assert get_page_by_id("does_not_exist") is None
    assert get_page_by_nav_key("Datasets") is get_page_by_id("datasets")
    data_pages = pages_for_mode("data")
    assert all(page.mode == "data" for page in data_pages)
    assert len(data_pages) > 0


def test_pages_are_json_serializable_for_snapshotting() -> None:
    for page in DASHBOARD_PAGES:
        json.dumps(
            {
                "page_id": page.page_id,
                "nav_key": page.nav_key,
                "title": page.title,
                "purpose": page.purpose,
                "tabs": list(page.tabs),
            }
        )


def test_action_registry_has_one_action_per_risk_tier_present() -> None:
    risk_levels_present = {action.risk_level for action in ACTION_DEFINITIONS}
    assert risk_levels_present <= set(RISK_LEVELS)
    assert "low" in risk_levels_present
    assert "moderate" in risk_levels_present
    assert "high" in risk_levels_present


def test_blocked_action_substrings_reject_train_and_pretrain() -> None:
    assert is_blocked_action_type("start_training")
    assert is_blocked_action_type("resume_pretrain_job")
    assert not is_blocked_action_type("dataset_record_review")


def test_is_known_action_type_matches_registry() -> None:
    assert is_known_action_type("dataset_record_review")
    assert is_known_action_type("dataset_source_update")
    assert is_known_action_type("governance_target_approval_override")
    assert not is_known_action_type("does_not_exist")
    assert not is_known_action_type("start_training")


def test_get_action_definition_and_filters() -> None:
    action = get_action_definition("governance_target_approval_override")
    assert action is not None
    assert action.risk_level == "high"
    assert action.requires_reason is True
    assert action.target_type == "governance_entity"

    governance_actions = actions_for_mode("governance")
    assert any(a.action_type == "governance_target_approval_override" for a in governance_actions)

    high_risk = actions_for_risk_level("high")
    assert all(a.risk_level == "high" for a in high_risk)


def test_action_definitions_are_json_serializable() -> None:
    for action in ACTION_DEFINITIONS:
        json.dumps(
            {
                "action_type": action.action_type,
                "target_type": action.target_type,
                "risk_level": action.risk_level,
                "payload_fields": list(action.payload_fields),
                "summary": action.summary,
                "confirmation_text": action.confirmation_text,
            }
        )


def test_admin_assistant_page_help_documents_the_response_language_preference() -> None:
    from core_model.admin_assistant.localization import to_tanglish

    page = get_page_by_id("admin_assistant")
    assert "Reply language" in page.purpose["en"]
    assert all(mode in page.purpose["en"] for mode in ("Tamil", "English", "Tanglish", "Auto"))
    assert "Reply language" in page.purpose["ta"]

    tanglish_purpose = to_tanglish(page.purpose["ta"])
    tamil_range = range(0x0B80, 0x0C00)
    assert not any(ord(ch) in tamil_range for ch in tanglish_purpose)


# --- Document SFT deep-link / navigation-target parity (Production Closure) -----------------


def test_documents_page_entry_tabs_match_the_real_frontend_tabs_exactly() -> None:
    real_tabs = _real_documents_page_tabs()
    page = get_page_by_id("documents")
    assert list(page.tabs) == real_tabs


def test_document_navigation_targets_have_no_duplicate_keys() -> None:
    keys = [target.tab_key for target in DOCUMENT_NAVIGATION_TARGETS]
    assert len(keys) == len(set(keys))
    assert len(NAVIGATION_TARGET_BY_KEY) == len(DOCUMENT_NAVIGATION_TARGETS)


def test_every_document_navigation_target_nav_key_is_a_registered_page() -> None:
    for target in DOCUMENT_NAVIGATION_TARGETS:
        assert get_page_by_nav_key(target.nav_key) is not None, (
            f"{target.tab_key} points at unregistered nav_key {target.nav_key!r}"
        )


def test_every_document_navigation_target_declares_at_most_one_kind_of_destination() -> None:
    for target in DOCUMENT_NAVIGATION_TARGETS:
        assert not (target.documents_tab and target.wizard_step), (
            f"{target.tab_key} declares both a documents_tab and a wizard_step"
        )


def test_every_documents_tab_target_maps_to_a_real_documents_page_tab() -> None:
    real_tabs = set(_real_documents_page_tabs())
    for target in DOCUMENT_NAVIGATION_TARGETS:
        if target.documents_tab is not None:
            assert target.documents_tab in real_tabs, (
                f"{target.tab_key} points at non-existent Documents tab {target.documents_tab!r}"
            )


def test_every_wizard_step_target_is_within_the_real_fourteen_step_range() -> None:
    for target in DOCUMENT_NAVIGATION_TARGETS:
        if target.wizard_step is not None:
            assert 1 <= target.wizard_step <= 14


def test_frontend_document_navigation_registry_matches_python_exactly() -> None:
    frontend = _frontend_document_nav_targets()
    python_keys = set(NAVIGATION_TARGET_BY_KEY)
    assert set(frontend) == python_keys
    for key, entry in frontend.items():
        target = NAVIGATION_TARGET_BY_KEY[key]
        assert entry["navKey"] == target.nav_key, key
        assert entry.get("documentsTab") == target.documents_tab, key
        assert entry.get("wizardStep") == target.wizard_step, key


def test_no_fabricated_history_navigation_key_exists() -> None:
    # "history" was explicitly considered and rejected in the closure audit
    # -- no History tab/section exists anywhere in Documents or the Wizard.
    assert resolve_document_navigation("history") is None
    assert "history" not in NAVIGATION_TARGET_BY_KEY


def test_admin_assistant_document_nav_keywords_are_a_subset_of_the_registry() -> None:
    from backend.services.admin_assistant_chat_service import AdminAssistantChatService

    for tab_key in AdminAssistantChatService._DOCUMENT_NAV_KEYWORDS:
        assert tab_key in NAVIGATION_TARGET_BY_KEY, (
            f"chat service references unregistered navigation key {tab_key!r}"
        )


def test_admin_assistant_nav_tool_map_only_uses_registered_tab_keys() -> None:
    from backend.services.admin_assistant_chat_service import AdminAssistantChatService

    for tab_key in AdminAssistantChatService._DOCUMENT_NAV_TOOL_BY_TAB_KEY:
        assert tab_key in NAVIGATION_TARGET_BY_KEY


def test_resolve_document_navigation_never_returns_a_fabricated_page_id() -> None:
    known_page_ids = {page.page_id for page in DASHBOARD_PAGES}
    for target in DOCUMENT_NAVIGATION_TARGETS:
        payload = resolve_document_navigation(target.tab_key, "doc-x")
        assert payload["page_id"] in known_page_ids
