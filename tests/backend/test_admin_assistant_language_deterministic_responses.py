"""End-to-end coverage of Phase 10A's own explicit test list (Step 17,
"Deterministic responses"): a saved preference must override the
input message's language across every existing deterministic reply
path, and every reply must stay free of the other scripts once
resolved.
"""

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.external_data_providers import (
    ExternalDataProviderRepository,
)
from backend.services.admin_assistant_chat_service import AdminAssistantChatService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
TAMIL_RANGE = range(0x0B80, 0x0C00)
ENGLISH_MESSAGE = "What is pending right now?"
TAMIL_MESSAGE = "இப்போது என்ன நிலுவையில் உள்ளது?"


def _has_tamil_script(text: str) -> bool:
    return any(ord(ch) in TAMIL_RANGE for ch in text)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "lang_e2e.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    with database_connection(settings.resolved_database_path) as connection:
        connection.execute(
            "INSERT INTO admin_accounts(public_id, username, display_name, password_hash) "
            "VALUES (?,?,?,?)",
            (ADMIN_ID, "e2e-lang-admin", "E2E Lang Admin", "hash"),
        )
        connection.commit()
    return settings


@pytest.fixture
def service(settings: Settings) -> AdminAssistantChatService:
    return AdminAssistantChatService(settings)


def _set_preference(settings: Settings, response_language: str) -> None:
    AdminRepository(settings.resolved_database_path).set_response_language(
        ADMIN_ID, response_language
    )


# -- pending-work summary --------------------------------------------------


def test_tamil_preference_with_english_input_returns_tamil_pending_work(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _set_preference(settings, "tamil")
    result = service.send_message(admin_id=ADMIN_ID, message=ENGLISH_MESSAGE, page_id="overview")
    assert result["resolved_language"] == "tamil"
    assert result["language_source"] == "saved_admin_preference"
    assert _has_tamil_script(result["answer"])


def test_english_preference_with_tamil_input_returns_english_pending_work(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _set_preference(settings, "english")
    result = service.send_message(admin_id=ADMIN_ID, message=TAMIL_MESSAGE, page_id="overview")
    assert result["resolved_language"] == "english"
    assert not _has_tamil_script(result["answer"])


def test_tanglish_preference_with_tamil_input_returns_latin_script_tanglish(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _set_preference(settings, "tanglish")
    result = service.send_message(admin_id=ADMIN_ID, message=TAMIL_MESSAGE, page_id="overview")
    assert result["resolved_language"] == "tanglish"
    assert not _has_tamil_script(result["answer"])


def test_auto_preference_follows_the_current_messages_language(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _set_preference(settings, "auto")
    tamil_result = service.send_message(
        admin_id=ADMIN_ID, message=TAMIL_MESSAGE, page_id="overview"
    )
    assert tamil_result["resolved_language"] == "tamil"
    english_result = service.send_message(
        admin_id=ADMIN_ID, message=ENGLISH_MESSAGE, page_id="overview"
    )
    assert english_result["resolved_language"] == "english"


# -- page help ("warnings"/"recommendations"-style deterministic text) -----


def test_tamil_preference_localizes_page_help(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _set_preference(settings, "tamil")
    result = service.send_message(
        admin_id=ADMIN_ID, message="help me with this page", page_id="external_data_providers"
    )
    assert result["intent"] == "help"
    assert _has_tamil_script(result["answer"])


def test_tanglish_preference_localizes_page_help(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _set_preference(settings, "tanglish")
    result = service.send_message(
        admin_id=ADMIN_ID, message="help me with this page", page_id="external_data_providers"
    )
    assert result["intent"] == "help"
    assert not _has_tamil_script(result["answer"])


# -- navigation --------------------------------------------------------------


def test_navigation_reply_is_localized_but_nav_key_stays_english(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _set_preference(settings, "tamil")
    result = service.send_message(
        admin_id=ADMIN_ID, message="go to Dataset Discovery", page_id="overview"
    )
    assert result["intent"] == "navigation"
    assert _has_tamil_script(result["answer"])
    assert "Dataset Discovery" in result["answer"]


# -- provider guidance ---------------------------------------------------------


def test_provider_lookup_is_localized_in_tanglish_and_preserves_provider_name(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    ExternalDataProviderRepository(settings.resolved_database_path).list_providers()
    _set_preference(settings, "tanglish")
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="Tell me about the AI4Bharat provider",
        page_id="external_data_providers",
    )
    assert not _has_tamil_script(result["answer"])
    assert "AI4Bharat" in result["answer"]


# -- dataset-discovery guidance -------------------------------------------------


def test_dataset_discovery_guidance_is_localized_in_tamil(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _set_preference(settings, "tamil")
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="Can you find a dataset for Tamil speech recognition?",
        page_id="dataset_discovery",
    )
    assert _has_tamil_script(result["answer"])
    assert result["navigation_target"]["page_id"] == "dataset_discovery"


# -- fallback (LLM unavailable) response ---------------------------------------


def test_generation_unavailable_fallback_is_localized_in_tanglish(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _set_preference(settings, "tanglish")
    result = service.send_message(
        admin_id=ADMIN_ID,
        message="Why did the last evaluation run score lower than expected?",
        page_id="evaluation",
    )
    assert result["status"] == "generation_failed"
    assert not _has_tamil_script(result["answer"])


# -- greeting -------------------------------------------------------------------


def test_greeting_is_localized_per_saved_preference_regardless_of_input_language(
    settings: Settings, service: AdminAssistantChatService
) -> None:
    _set_preference(settings, "english")
    result = service.send_message(admin_id=ADMIN_ID, message="வணக்கம்", page_id="overview")
    assert result["intent"] == "greeting"
    assert not _has_tamil_script(result["answer"])
    assert "Hello" in result["answer"]
