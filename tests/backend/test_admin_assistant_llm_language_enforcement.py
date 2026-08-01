from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.services.admin_assistant_chat_service import (
    LLM_LANGUAGE_INSTRUCTIONS,
    AdminAssistantChatService,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "llm_language.db",
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
            (ADMIN_ID, "llm-test-admin", "LLM Test Admin", "hash"),
        )
        connection.commit()
    return settings


@pytest.fixture
def service(settings: Settings) -> AdminAssistantChatService:
    return AdminAssistantChatService(settings)


def _fake_instance():
    return {
        "public_id": "instance-1",
        "profile_maximum_new_tokens": 64,
        "profile_request_timeout_seconds": 5,
    }


def _wire_assignment(service: AdminAssistantChatService) -> None:
    service._resolve_admin_diagnostic_assignment = lambda: {"public_id": "assignment-1"}
    service._assignment_service.ensure_instance_loaded = lambda *args, **kwargs: _fake_instance()


def test_llm_language_instructions_cover_every_concrete_language() -> None:
    assert set(LLM_LANGUAGE_INSTRUCTIONS) == {"tamil", "english", "tanglish"}
    assert "auto" not in LLM_LANGUAGE_INSTRUCTIONS


def test_generate_llm_reply_raises_on_unresolved_auto(service: AdminAssistantChatService) -> None:
    _wire_assignment(service)
    with pytest.raises(KeyError):
        service._generate_llm_reply(
            message="hi", context_text="", admin_id=ADMIN_ID, resolved_language="auto"
        )


def test_generate_llm_reply_injects_resolved_language_into_system_prompt(
    service: AdminAssistantChatService,
) -> None:
    _wire_assignment(service)
    captured = {}

    def fake_run_generation(
        instance_public_id, *, prompt_text, maximum_new_tokens, timeout_seconds, system_text
    ):
        captured["system_text"] = system_text
        return {"generated_text": "This dataset is ready for training."}

    service._runtime_service.run_generation = fake_run_generation
    result = service._generate_llm_reply(
        message="Is this ready?", context_text="", admin_id=ADMIN_ID, resolved_language="english"
    )
    assert result == "This dataset is ready for training."
    assert LLM_LANGUAGE_INSTRUCTIONS["english"] in captured["system_text"]


def test_generate_llm_reply_retries_once_on_language_mismatch_then_succeeds(
    service: AdminAssistantChatService,
) -> None:
    _wire_assignment(service)
    calls = []

    def fake_run_generation(
        instance_public_id, *, prompt_text, maximum_new_tokens, timeout_seconds, system_text
    ):
        calls.append(prompt_text)
        if len(calls) == 1:
            return {"generated_text": "இது ஒரு முழுமையான தமிழ் வாக்கியம் இங்கே உள்ளது."}
        return {"generated_text": "This is the correct English reply after the retry."}

    service._runtime_service.run_generation = fake_run_generation
    result = service._generate_llm_reply(
        message="Is this ready?", context_text="", admin_id=ADMIN_ID, resolved_language="english"
    )
    assert result == "This is the correct English reply after the retry."
    assert len(calls) == 2


def test_generate_llm_reply_returns_none_after_two_language_mismatches(
    service: AdminAssistantChatService,
) -> None:
    _wire_assignment(service)
    calls = []

    def fake_run_generation(
        instance_public_id, *, prompt_text, maximum_new_tokens, timeout_seconds, system_text
    ):
        calls.append(prompt_text)
        return {"generated_text": "இது எப்போதும் தமிழில் மட்டுமே பதிலளிக்கும் ஒரு உரை."}

    service._runtime_service.run_generation = fake_run_generation
    result = service._generate_llm_reply(
        message="Is this ready?", context_text="", admin_id=ADMIN_ID, resolved_language="english"
    )
    assert result is None
    assert len(calls) == 2


def test_generate_llm_reply_returns_none_when_no_assignment_configured(
    service: AdminAssistantChatService,
) -> None:
    service._resolve_admin_diagnostic_assignment = lambda: None
    result = service._generate_llm_reply(
        message="hi", context_text="", admin_id=ADMIN_ID, resolved_language="tamil"
    )
    assert result is None


def test_generate_llm_reply_accepts_tanglish_output_for_tanglish_mode(
    service: AdminAssistantChatService,
) -> None:
    _wire_assignment(service)
    service._runtime_service.run_generation = lambda *a, **k: {
        "generated_text": "Indha dataset innum training-ku ready illa."
    }
    result = service._generate_llm_reply(
        message="ready-a?", context_text="", admin_id=ADMIN_ID, resolved_language="tanglish"
    )
    assert result == "Indha dataset innum training-ku ready illa."
