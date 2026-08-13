"""MB-27: service-level tests for MiniBrainProviderSettingsService
against a real temp SQLite DB -- no mocks of the repository. Only the
network adapter is ever substituted (with `MockConnectionAdapter`),
never the service or repository layers themselves.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.services import mini_brain_provider_settings_service as service_module
from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService
from backend.services.provider_settings_connection_adapters import MockConnectionAdapter
from core_model.mini_brain.provider_settings import secret_encryptor


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    result = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    return result


@pytest.fixture
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> bytes:
    key = Fernet.generate_key()
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, key.decode("ascii"))
    return key


@pytest.fixture
def mock_adapter_factory(monkeypatch: pytest.MonkeyPatch):
    def _install(*, status: str = "success", latency_ms: float = 4.2, error_message: str | None = None):
        monkeypatch.setattr(
            service_module, "adapter_for_provider",
            lambda provider_key: MockConnectionAdapter(provider_key=provider_key, status=status, latency_ms=latency_ms, error_message=error_message),
        )
    return _install


def test_create_provider_setting(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    result = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    assert result["provider_key"] == "openai"
    assert result["enabled"] is False
    assert result["secrets"] == []


def test_create_duplicate_provider_setting_raises(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    with pytest.raises(ValidationError):
        service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")


def test_create_unknown_provider_raises(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    with pytest.raises(ValidationError):
        service.create_provider_setting(provider_key="bogus", enabled=False, config={}, admin_id="admin-1")


def test_create_with_invalid_config_key_raises(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    with pytest.raises(ValidationError):
        service.create_provider_setting(provider_key="openai", enabled=False, config={"not_real": 1}, admin_id="admin-1")


def test_update_provider_setting_config(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    updated = service.update_provider_setting(created["public_id"], config={"model": "gpt-4o-mini"}, admin_id="admin-1")
    assert updated["config"] == {"model": "gpt-4o-mini"}


def test_get_setting_not_found_raises(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    with pytest.raises(NotFoundError):
        service.get_setting("00000000-0000-0000-0000-000000000000")


def test_list_settings_empty(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    assert service.list_settings()["items"] == []


def test_list_settings_filters_by_provider_type(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    service.create_provider_setting(provider_key="faster_whisper", enabled=True, config={}, admin_id="admin-1")
    external = service.list_settings(provider_type="external_ai")["items"]
    assert len(external) == 1
    assert external[0]["provider_key"] == "openai"


# -- secrets ------------------------------------------------------------------------------


def test_set_secret_encrypts_before_db_write(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="sk-real-value-12345", admin_id="admin-1")

    conn = sqlite3.connect(settings.resolved_database_path)
    row = conn.execute(
        "SELECT encrypted_value FROM mini_brain_provider_secrets WHERE setting_public_id=?", (created["public_id"],)
    ).fetchone()
    conn.close()
    assert row is not None
    stored_value = row[0]
    assert "sk-real-value-12345" not in stored_value
    # genuine ciphertext: decrypting with the RIGHT key recovers the plaintext...
    assert secret_encryptor.decrypt_secret(stored_value) == "sk-real-value-12345"


def test_set_secret_stored_value_fails_to_decrypt_with_wrong_key(settings: Settings, fernet_key: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="sk-real-value-12345", admin_id="admin-1")

    conn = sqlite3.connect(settings.resolved_database_path)
    row = conn.execute(
        "SELECT encrypted_value FROM mini_brain_provider_secrets WHERE setting_public_id=?", (created["public_id"],)
    ).fetchone()
    conn.close()

    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, Fernet.generate_key().decode("ascii"))
    with pytest.raises(secret_encryptor.SecretDecryptionError):
        secret_encryptor.decrypt_secret(row[0])


def test_set_secret_without_encryption_key_raises(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, raising=False)
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    with pytest.raises(secret_encryptor.EncryptionUnavailableError):
        service.set_secret(created["public_id"], secret_name="api_key", raw_value="x", admin_id="admin-1")


def test_get_setting_never_contains_encrypted_value(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="sk-real-value-12345", admin_id="admin-1")
    fetched = service.get_setting(created["public_id"])
    serialized = json.dumps(fetched)
    assert "encrypted_value" not in serialized
    assert "sk-real-value-12345" not in serialized


def test_delete_secret(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="sk-x", admin_id="admin-1")
    updated = service.delete_secret(created["public_id"], secret_name="api_key", admin_id="admin-1")
    assert updated["secrets"] == []


def test_masked_secret_indicator_is_fixed_width(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="a", admin_id="admin-1")
    short = service.get_setting(created["public_id"])["secrets"][0]["masked_indicator"]
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="a" * 200, admin_id="admin-1")
    long = service.get_setting(created["public_id"])["secrets"][0]["masked_indicator"]
    assert short == long


# -- enable / disable / archive ------------------------------------------------------------


def test_enable_disable_provider(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    enabled = service.enable_provider(created["public_id"], admin_id="admin-1")
    assert enabled["enabled"] is True
    disabled = service.disable_provider(created["public_id"], admin_id="admin-1")
    assert disabled["enabled"] is False


def test_archive_provider_setting(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    archived = service.archive_provider_setting(created["public_id"], admin_id="admin-1")
    assert archived["enabled"] is False
    # archived settings excluded from default list
    assert created["public_id"] not in [item["public_id"] for item in service.list_settings()["items"]]


# -- connection test ------------------------------------------------------------------------


def test_connection_test_success(settings: Settings, fernet_key: bytes, mock_adapter_factory) -> None:
    mock_adapter_factory(status="success", latency_ms=3.3)
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="sk-x", admin_id="admin-1")
    result = service.test_connection(created["public_id"], admin_id="admin-1")
    assert result["status"] == "success"
    assert result["latency_ms"] == 3.3


def test_connection_test_result_never_contains_secret_or_key_field(settings: Settings, fernet_key: bytes, mock_adapter_factory) -> None:
    mock_adapter_factory(status="success")
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="sk-super-secret-value", admin_id="admin-1")
    result = service.test_connection(created["public_id"], admin_id="admin-1")
    serialized = json.dumps(result)
    assert "sk-super-secret-value" not in serialized
    assert "decrypted_api_key" not in serialized
    assert "api_key" not in result


def test_connection_test_missing_secret_returns_missing_key(settings: Settings, fernet_key: bytes, mock_adapter_factory) -> None:
    mock_adapter_factory(status="success")
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    result = service.test_connection(created["public_id"], admin_id="admin-1")
    assert result["status"] == "missing_key"


def test_connection_test_writes_audit_and_memory(settings: Settings, fernet_key: bytes, mock_adapter_factory) -> None:
    mock_adapter_factory(status="success")
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    service.test_connection(created["public_id"], admin_id="admin-1")
    audit = service.list_audit_events(created["public_id"])["items"]
    assert any(event["action"] == "test_connection" for event in audit)
    memory = service.list_memory()["items"]
    assert any(row["event_type"] == "test_connection_run" for row in memory)


# -- export / import ------------------------------------------------------------------------


def test_export_excludes_secrets(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="sk-should-never-export", admin_id="admin-1")
    exported = service.export_settings()
    serialized = json.dumps(exported)
    assert "sk-should-never-export" not in serialized
    assert "encrypted_value" not in serialized
    assert "secrets" not in serialized


def test_export_never_calls_list_secrets(settings: Settings, fernet_key: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    service = MiniBrainProviderSettingsService(settings)
    service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")

    called = {"list_secrets": False}
    original = service.repository.list_secrets

    def _tracking_list_secrets(*args, **kwargs):
        called["list_secrets"] = True
        return original(*args, **kwargs)

    monkeypatch.setattr(service.repository, "list_secrets", _tracking_list_secrets)
    service.export_settings()
    assert called["list_secrets"] is False


def test_import_settings_metadata_updates_enabled(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    result = service.import_settings_metadata({"providers": [{"provider_key": "openai", "enabled": False}]}, admin_id="admin-1")
    assert result["items"][0]["enabled"] is False


def test_import_settings_metadata_rejects_forbidden_field(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    with pytest.raises(ValidationError):
        service.import_settings_metadata({"providers": [{"provider_key": "openai", "encrypted_value": "x"}]}, admin_id="admin-1")


# -- diagnostics --------------------------------------------------------------------------


def test_diagnostics_missing_encryption_key(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, raising=False)
    service = MiniBrainProviderSettingsService(settings)
    diag = service.diagnostics()
    assert diag["missing_encryption_key"] is True
    assert diag["encryption_available"] is False


def test_diagnostics_counts(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    service.create_provider_setting(provider_key="anthropic", enabled=False, config={}, admin_id="admin-1")
    diag = service.diagnostics()
    assert diag["configured_provider_count"] == 2
    assert diag["enabled_provider_count"] == 1


def test_diagnostics_never_contains_secret_material(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="sk-diag-test-value", admin_id="admin-1")
    diag = service.diagnostics()
    assert "sk-diag-test-value" not in json.dumps(diag)


# -- audit trail ----------------------------------------------------------------------------


def test_audit_events_created_on_full_lifecycle(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="sk-x", admin_id="admin-1")
    service.enable_provider(created["public_id"], admin_id="admin-1")
    service.disable_provider(created["public_id"], admin_id="admin-1")
    service.delete_secret(created["public_id"], secret_name="api_key", admin_id="admin-1")
    service.archive_provider_setting(created["public_id"], admin_id="admin-1")

    audit = service.list_audit_events(created["public_id"])["items"]
    actions = {event["action"] for event in audit}
    assert actions == {"created", "secret_set", "enabled", "disabled", "secret_deleted", "archived"}


def test_audit_events_never_contain_secret_values(settings: Settings, fernet_key: bytes) -> None:
    service = MiniBrainProviderSettingsService(settings)
    created = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    service.set_secret(created["public_id"], secret_name="api_key", raw_value="sk-audit-test-value", admin_id="admin-1")
    audit = service.list_audit_events(created["public_id"])["items"]
    assert "sk-audit-test-value" not in json.dumps(audit)
    secret_set_event = next(event for event in audit if event["action"] == "secret_set")
    assert secret_set_event["changed_fields"] == ["secret:api_key"]
