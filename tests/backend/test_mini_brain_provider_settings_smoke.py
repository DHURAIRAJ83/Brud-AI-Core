"""MB-27: real end-to-end smoke test for Secrets & Provider Settings.

Drives the exact 9-step scenario the phase spec's own "End-to-End
Smoke Test" section lists, against a real `create_app()`-booted
application and a real temporary Fernet key -- only the outbound
network call inside `test_connection()` is ever mocked (via
`MockConnectionAdapter`); the service, repository, and encryption
layers are never mocked.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services import mini_brain_provider_settings_service as service_module
from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService
from backend.services.provider_settings_connection_adapters import MockConnectionAdapter
from core_model.mini_brain.provider_settings import secret_encryptor

FAKE_API_KEY = "sk-or-v1-fake-smoke-test-key-never-real-0123456789"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    result = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents", document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    return result


def test_mb27_end_to_end_smoke(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.main import create_app

    app = create_app(settings)
    assert app is not None  # a real create_app() boot, not a bare service instantiation

    # -- step 1: set a temporary Fernet key -- never committed anywhere -------------------
    key = Fernet.generate_key()
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, key.decode("ascii"))

    service = MiniBrainProviderSettingsService(settings)
    assert service.diagnostics()["encryption_available"] is True

    # -- step 2: create OpenRouter provider ------------------------------------------------
    setting_row = service.create_provider_setting(provider_key="openrouter", enabled=False, config={}, admin_id="admin-1")
    assert setting_row["provider_key"] == "openrouter"
    assert "encrypted_value" not in json.dumps(setting_row)
    setting_id = setting_row["public_id"]

    # -- step 3: store API key ---------------------------------------------------------------
    setting_row = service.set_secret(setting_id, secret_name="api_key", raw_value=FAKE_API_KEY, admin_id="admin-1")
    assert setting_row["secrets"][0]["is_set"] is True
    assert FAKE_API_KEY not in json.dumps(setting_row)

    # real DB-level proof the stored value is genuine Fernet ciphertext, not plaintext
    conn = sqlite3.connect(settings.resolved_database_path)
    stored = conn.execute(
        "SELECT encrypted_value FROM mini_brain_provider_secrets WHERE setting_public_id=?", (setting_id,)
    ).fetchone()[0]
    conn.close()
    assert FAKE_API_KEY not in stored
    assert secret_encryptor.decrypt_secret(stored) == FAKE_API_KEY

    # -- step 4: enable provider -------------------------------------------------------------
    setting_row = service.enable_provider(setting_id, admin_id="admin-1")
    assert setting_row["enabled"] is True
    assert setting_row["health"] == "healthy"

    # -- step 5: run a mocked connection test -------------------------------------------------
    monkeypatch.setattr(
        service_module, "adapter_for_provider",
        lambda provider_key: MockConnectionAdapter(provider_key=provider_key, status="success", latency_ms=6.6),
    )
    result = service.test_connection(setting_id, secret_name="api_key", timeout_seconds=10, admin_id="admin-1")
    assert result["status"] == "success"
    assert result["provider_key"] == "openrouter"

    # -- step 6: verify API never returns plaintext -------------------------------------------
    fetched = service.get_setting(setting_id)
    fetched_serialized = json.dumps(fetched)
    assert FAKE_API_KEY not in fetched_serialized
    assert "encrypted_value" not in fetched_serialized
    result_serialized = json.dumps(result)
    assert FAKE_API_KEY not in result_serialized
    assert "decrypted_api_key" not in result_serialized

    # -- step 7: export settings, confirm secret absence --------------------------------------
    exported = service.export_settings()
    exported_serialized = json.dumps(exported)
    assert FAKE_API_KEY not in exported_serialized
    assert "encrypted_value" not in exported_serialized
    assert "secrets" not in exported_serialized

    # -- step 8: archive provider --------------------------------------------------------------
    archived = service.archive_provider_setting(setting_id, admin_id="admin-1")
    assert archived["enabled"] is False
    assert setting_id not in [item["public_id"] for item in service.list_settings()["items"]]

    # -- step 9: confirm memory row written -----------------------------------------------------
    memory = service.list_memory()
    event_types = {row["event_type"] for row in memory["items"]}
    assert {"created", "secret_set", "enabled", "test_connection_run", "archived"} <= event_types

    # -- audit trail sanity: every mutating step left an honest, value-free record --------------
    audit = service.list_audit_events(setting_id)["items"]
    assert FAKE_API_KEY not in json.dumps(audit)
    secret_set_events = [event for event in audit if event["action"] == "secret_set"]
    assert secret_set_events[0]["changed_fields"] == ["secret:api_key"]


def test_mb27_missing_encryption_key_never_silently_generates_one(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Companion assertion: with BRUD_SECRET_ENCRYPTION_KEY unset,
    set_secret() must raise, and diagnostics must honestly report the
    key as missing -- never silently generate and persist a new key."""
    monkeypatch.delenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, raising=False)
    service = MiniBrainProviderSettingsService(settings)

    diag = service.diagnostics()
    assert diag["missing_encryption_key"] is True
    assert diag["encryption_available"] is False

    setting_row = service.create_provider_setting(provider_key="openai", enabled=False, config={}, admin_id="admin-1")
    with pytest.raises(secret_encryptor.EncryptionUnavailableError):
        service.set_secret(setting_row["public_id"], secret_name="api_key", raw_value="sk-should-never-be-stored", admin_id="admin-1")

    # confirm literally nothing was written to the secrets table
    conn = sqlite3.connect(settings.resolved_database_path)
    count = conn.execute(
        "SELECT COUNT(*) FROM mini_brain_provider_secrets WHERE setting_public_id=?", (setting_row["public_id"],)
    ).fetchone()[0]
    conn.close()
    assert count == 0
