from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.models.auth import AdminCreate
from backend.services.admin_assistant_language_service import AdminAssistantLanguageService

ENGLISH_MESSAGE = "Is this dataset ready for training?"
TAMIL_MESSAGE = "இந்த தரவுத்தொகுப்பு பயிற்சிக்கு தயாராக உள்ளதா?"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "language.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def admin_id(settings: Settings) -> str:
    admin = AdminRepository(settings.resolved_database_path).create_admin(
        AdminCreate(username="lang-admin", display_name="Language Admin", password="Lang-Pass-42")
    )
    return admin.public_id


@pytest.fixture
def service(settings: Settings) -> AdminAssistantLanguageService:
    return AdminAssistantLanguageService(settings)


def test_new_admin_defaults_to_auto(
    service: AdminAssistantLanguageService, admin_id: str
) -> None:
    preference = service.get_preference(admin_id)
    assert preference["response_language"] == "auto"


def test_set_and_get_preference_round_trip(
    service: AdminAssistantLanguageService, admin_id: str
) -> None:
    updated = service.set_preference(admin_id, "tanglish")
    assert updated["response_language"] == "tanglish"
    assert updated["updated_at"]

    fetched = service.get_preference(admin_id)
    assert fetched["response_language"] == "tanglish"


def test_set_preference_rejects_invalid_enum(
    service: AdminAssistantLanguageService, admin_id: str
) -> None:
    with pytest.raises(ValidationError):
        service.set_preference(admin_id, "klingon")


def test_set_preference_unknown_admin_raises(service: AdminAssistantLanguageService) -> None:
    with pytest.raises(NotFoundError):
        service.set_preference("does-not-exist", "tamil")


def test_preferences_are_isolated_per_admin(settings: Settings) -> None:
    repository = AdminRepository(settings.resolved_database_path)
    admin_a = repository.create_admin(
        AdminCreate(username="admin-a", display_name="Admin A", password="Password-A-42")
    )
    admin_b = repository.create_admin(
        AdminCreate(username="admin-b", display_name="Admin B", password="Password-B-42")
    )
    service = AdminAssistantLanguageService(settings)
    service.set_preference(admin_a.public_id, "tamil")
    service.set_preference(admin_b.public_id, "english")

    assert service.get_preference(admin_a.public_id)["response_language"] == "tamil"
    assert service.get_preference(admin_b.public_id)["response_language"] == "english"


def test_set_preference_change_is_audited(settings: Settings, admin_id: str) -> None:
    service = AdminAssistantLanguageService(settings)
    service.set_preference(admin_id, "tanglish")
    with database_connection(settings.resolved_database_path) as connection:
        row = connection.execute(
            "SELECT metadata_json FROM audit_logs WHERE event_type=? AND actor_reference=?",
            ("admin_assistant_response_language_changed", admin_id),
        ).fetchone()
    assert row is not None
    assert '"new_response_language":"tanglish"' in row["metadata_json"]
    assert '"old_response_language":"auto"' in row["metadata_json"]
    assert TAMIL_MESSAGE not in row["metadata_json"]


def test_resolve_uses_saved_preference_over_message_language(
    service: AdminAssistantLanguageService, admin_id: str
) -> None:
    service.set_preference(admin_id, "english")
    resolved = service.resolve(admin_id=admin_id, message_text=TAMIL_MESSAGE)
    assert resolved.resolved_language == "english"
    assert resolved.source == "saved_admin_preference"


def test_resolve_auto_detects_from_message(
    service: AdminAssistantLanguageService, admin_id: str
) -> None:
    resolved = service.resolve(admin_id=admin_id, message_text=ENGLISH_MESSAGE)
    assert resolved.configured_mode == "auto"
    assert resolved.resolved_language == "english"


def test_preview_never_persists_a_preference(
    service: AdminAssistantLanguageService, admin_id: str
) -> None:
    before = service.get_preference(admin_id)["response_language"]
    result = service.preview(message_text=TAMIL_MESSAGE, request_override="tanglish")
    assert result["resolved_language"] == "tanglish"
    after = service.get_preference(admin_id)["response_language"]
    assert after == before
