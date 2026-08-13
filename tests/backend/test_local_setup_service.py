"""MB-29: service-layer tests for LocalSetupService -- real database,
real MB-27 provider settings service, real temporary model directories.
No mocking anywhere in this file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.services.local_setup_service import LocalSetupService
from core_model.mini_brain.provider_settings import secret_encryptor


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    allowed = tmp_path / "models"
    allowed.mkdir()
    result = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports", allowed_model_dir=allowed,
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    return result


@pytest.fixture
def service(settings: Settings) -> LocalSetupService:
    return LocalSetupService(settings)


@pytest.fixture
def fernet_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, Fernet.generate_key().decode("ascii"))


# -- hardware_summary -------------------------------------------------------------------


def test_hardware_summary_includes_health(service: LocalSetupService) -> None:
    result = service.hardware_summary()
    assert "health" in result
    assert result["health"]["health"] == "unconfigured"


# -- scan_local_models -------------------------------------------------------------------


def test_scan_local_models_empty(service: LocalSetupService) -> None:
    result = service.scan_local_models()
    assert result["items"] == []


def test_scan_local_models_finds_real_file(settings: Settings, service: LocalSetupService) -> None:
    (settings.resolved_allowed_model_dir / "model.gguf").write_bytes(b"x")
    result = service.scan_local_models()
    assert len(result["items"]) == 1


def test_scan_local_models_includes_additional_dirs(settings: Settings, tmp_path: Path, service: LocalSetupService) -> None:
    extra_dir = tmp_path / "extra_models"
    extra_dir.mkdir()
    (extra_dir / "extra.gguf").write_bytes(b"x")
    service.save_local_model_configuration(
        model_path=None, context_length=2048, max_tokens=512, temperature=0.3, threads=4,
        additional_model_dirs=[str(extra_dir)], admin_id="admin-1",
    )
    result = service.scan_local_models()
    assert any(item["filename"] == "extra.gguf" for item in result["items"])


def test_scan_local_models_deduplicates_overlapping_dirs(settings: Settings, service: LocalSetupService) -> None:
    (settings.resolved_allowed_model_dir / "model.gguf").write_bytes(b"x")
    service.save_local_model_configuration(
        model_path=None, context_length=2048, max_tokens=512, temperature=0.3, threads=4,
        additional_model_dirs=[str(settings.resolved_allowed_model_dir)], admin_id="admin-1",
    )
    result = service.scan_local_models()
    assert len(result["items"]) == 1  # not double-counted


# -- recommend_models -------------------------------------------------------------------


def test_recommend_models_returns_top_recommendation(service: LocalSetupService) -> None:
    result = service.recommend_models()
    assert result["top_recommendation"] is not None


# -- save_local_model_configuration -----------------------------------------------------


def test_save_local_model_configuration_creates_new_setting(settings: Settings, service: LocalSetupService) -> None:
    model_file = settings.resolved_allowed_model_dir / "model.gguf"
    model_file.write_bytes(b"x")
    saved = service.save_local_model_configuration(
        model_path=str(model_file), context_length=4096, max_tokens=256, temperature=0.5, threads=8, admin_id="admin-1",
    )
    assert saved["config"]["context_length"] == 4096
    assert saved["config"]["threads"] == 8


def test_save_local_model_configuration_updates_existing_setting(settings: Settings, service: LocalSetupService) -> None:
    model_file = settings.resolved_allowed_model_dir / "model.gguf"
    model_file.write_bytes(b"x")
    first = service.save_local_model_configuration(
        model_path=str(model_file), context_length=2048, max_tokens=512, temperature=0.3, threads=4, admin_id="admin-1",
    )
    second = service.save_local_model_configuration(
        model_path=str(model_file), context_length=8192, max_tokens=1024, temperature=0.7, threads=2, admin_id="admin-1",
    )
    assert first["public_id"] == second["public_id"]  # updated, not duplicated
    assert second["config"]["context_length"] == 8192


def test_save_local_model_configuration_preserves_additional_dirs_when_not_resupplied(
    settings: Settings, tmp_path: Path, service: LocalSetupService,
) -> None:
    extra_dir = tmp_path / "extra"
    extra_dir.mkdir()
    service.save_local_model_configuration(
        model_path=None, context_length=2048, max_tokens=512, temperature=0.3, threads=4,
        additional_model_dirs=[str(extra_dir)], admin_id="admin-1",
    )
    updated = service.save_local_model_configuration(
        model_path=None, context_length=4096, max_tokens=512, temperature=0.3, threads=4, admin_id="admin-1",
    )
    assert updated["config"]["additional_model_dirs"] == [str(extra_dir)]


def test_save_local_model_configuration_rejects_unconfined_path(settings: Settings, tmp_path: Path, service: LocalSetupService) -> None:
    outside = tmp_path / "outside.gguf"
    outside.write_bytes(b"x")
    with pytest.raises(ValidationError):
        service.save_local_model_configuration(
            model_path=str(outside), context_length=2048, max_tokens=512, temperature=0.3, threads=4, admin_id="admin-1",
        )


def test_save_local_model_configuration_allows_none_path(service: LocalSetupService) -> None:
    saved = service.save_local_model_configuration(
        model_path=None, context_length=2048, max_tokens=512, temperature=0.3, threads=4, admin_id="admin-1",
    )
    assert saved["config"]["model_path"] is None


# -- save_external_provider_configuration ------------------------------------------------


def test_save_external_provider_configuration_rejects_unknown_provider(service: LocalSetupService) -> None:
    with pytest.raises(ValidationError):
        service.save_external_provider_configuration(
            provider_key="bogus", api_key=None, model=None, enabled=False, admin_id="admin-1",
        )


def test_save_external_provider_configuration_creates_and_enables(
    service: LocalSetupService, fernet_key: None,
) -> None:
    saved = service.save_external_provider_configuration(
        provider_key="gemini", api_key="sk-real", model="gemini-1.5-flash", enabled=True, admin_id="admin-1",
    )
    assert saved["enabled"] is True
    assert saved["config"]["model"] == "gemini-1.5-flash"
    assert saved["secrets"][0]["is_set"] is True
    assert "sk-real" not in str(saved)


def test_save_external_provider_configuration_disable(service: LocalSetupService, fernet_key: None) -> None:
    service.save_external_provider_configuration(
        provider_key="openai", api_key="sk-real", model=None, enabled=True, admin_id="admin-1",
    )
    disabled = service.save_external_provider_configuration(
        provider_key="openai", api_key=None, model=None, enabled=False, admin_id="admin-1",
    )
    assert disabled["enabled"] is False


def test_save_external_provider_configuration_without_api_key_does_not_set_secret(service: LocalSetupService) -> None:
    saved = service.save_external_provider_configuration(
        provider_key="openrouter", api_key=None, model=None, enabled=False, admin_id="admin-1",
    )
    assert saved["secrets"] == []  # no secret row exists at all until one is actually set


# -- provider_catalog / build_setup_guide / diagnostics -----------------------------------


def test_provider_catalog(service: LocalSetupService) -> None:
    result = service.provider_catalog()
    assert len(result["providers"]) == 4


def test_build_setup_guide(service: LocalSetupService) -> None:
    guide = service.build_setup_guide()
    assert len(guide["steps"]) >= 2


def test_diagnostics_reflects_scan_and_config(settings: Settings, service: LocalSetupService) -> None:
    model_file = settings.resolved_allowed_model_dir / "model.gguf"
    model_file.write_bytes(b"x")
    service.save_local_model_configuration(
        model_path=str(model_file), context_length=2048, max_tokens=512, temperature=0.3, threads=4, admin_id="admin-1",
    )
    diagnostics = service.diagnostics()
    assert diagnostics["scanned_model_count"] == 1
    assert diagnostics["local_model_available"] is True
    assert diagnostics["configured_model_path"] == "model.gguf"
