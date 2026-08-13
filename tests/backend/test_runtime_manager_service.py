"""MB-30: service-layer tests for RuntimeManagerService -- real
database, real MB-27/28/29 service reuse, real temporary model
directories. The LLM backend itself is always `MockMiniBrainAdapter`
(injected via `adapter_factory=`); no real network call is made in
this file.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter
from backend.services.runtime_manager_service import RuntimeManagerService
from core_model.mini_brain.runtime_manager import checksum_verifier

_FAKE_HARDWARE = {
    "total_ram_gb": 6.0, "available_ram_gb": 4.5, "cpu_cores": 4, "cpu_threads": 4,
    "architecture": "x86_64", "os_name": "Linux", "disk_free_gb": 50.0, "python_version": "3.13.5",
    "recommended_ram_tier": "6GB", "psutil_available": True,
}


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
def service(settings: Settings) -> RuntimeManagerService:
    return RuntimeManagerService(settings, adapter_factory=lambda: MockMiniBrainAdapter())


def _install_fake_model(settings: Settings, service: RuntimeManagerService, model_id: str | None = None) -> tuple[str, dict]:
    recommendation = service.get_recommended_model()
    model_id = model_id or recommendation["model_id"]
    fake_bytes = b"fake-gguf" * 500
    model_file = settings.resolved_allowed_model_dir / recommendation["file_name"]
    model_file.write_bytes(fake_bytes)
    digest = checksum_verifier.compute_sha256(fake_bytes)
    installation = service.install_model(model_id, file_path=str(model_file), expected_sha256=digest, admin_id="admin-1")
    return model_id, installation


# -- detect_system ------------------------------------------------------------------


def test_detect_system_returns_real_hardware(service: RuntimeManagerService) -> None:
    result = service.detect_system()
    assert result["cpu_threads"] >= 1
    assert result["recommended_ram_tier"]


# -- list_installed_models / get_recommended_model -----------------------------------------


def test_list_installed_models_empty(service: RuntimeManagerService) -> None:
    assert service.list_installed_models()["items"] == []


def test_get_recommended_model_matches_catalog(service: RuntimeManagerService) -> None:
    result = service.get_recommended_model()
    assert result["model_id"] == "qwen2.5-1.5b-instruct-q4_k_m"
    assert result["tier"] == "recommended"


# -- create_download_plan --------------------------------------------------------------------


def test_create_download_plan_known_model(service: RuntimeManagerService, settings: Settings) -> None:
    plan = service.create_download_plan("qwen2.5-1.5b-instruct-q4_k_m")
    assert plan["target_path"].startswith(str(settings.resolved_allowed_model_dir))


def test_create_download_plan_unknown_model_raises(service: RuntimeManagerService) -> None:
    with pytest.raises(ValidationError):
        service.create_download_plan("bogus-model-id")


# -- download_model (mocked httpx) -----------------------------------------------------------


def test_download_model_mocked_success(service: RuntimeManagerService, settings: Settings) -> None:
    fake_bytes = b"fake-model-bytes" * 10000

    class FakeResponse:
        def raise_for_status(self):
            pass

        def iter_bytes(self, chunk_size=1024 * 1024):
            yield fake_bytes

    class FakeStreamContext:
        def __enter__(self):
            return FakeResponse()

        def __exit__(self, *args):
            return False

    with patch("httpx.stream", return_value=FakeStreamContext()):
        with patch("shutil.disk_usage") as mock_disk:
            mock_disk.return_value = type("Usage", (), {"free": 100_000_000_000, "total": 100_000_000_000, "used": 0})()
            result = service.download_model("qwen2.5-1.5b-instruct-q4_k_m", admin_id="admin-1")
    assert result["status"] == "installed"


def test_download_model_rejects_insufficient_disk(service: RuntimeManagerService) -> None:
    with patch("shutil.disk_usage") as mock_disk:
        mock_disk.return_value = type("Usage", (), {"free": 1_000, "total": 1_000, "used": 0})()
        with pytest.raises(ValidationError):
            service.download_model("qwen2.5-1.5b-instruct-q4_k_m", admin_id="admin-1")


def test_download_model_handles_network_failure_honestly(service: RuntimeManagerService) -> None:
    with patch("httpx.stream", side_effect=RuntimeError("connection refused")):
        with patch("shutil.disk_usage") as mock_disk:
            mock_disk.return_value = type("Usage", (), {"free": 100_000_000_000, "total": 100_000_000_000, "used": 0})()
            with pytest.raises(ValidationError):
                service.download_model("qwen2.5-1.5b-instruct-q4_k_m", admin_id="admin-1")
    events = service.list_events(model_name="qwen2.5-1.5b-instruct-q4_k_m")["items"]
    assert any(event["event_type"] == "download_failed" for event in events)


# -- verify_model ---------------------------------------------------------------------------


def test_verify_model_no_installation_raises(service: RuntimeManagerService) -> None:
    with pytest.raises(NotFoundError):
        service.verify_model("qwen2.5-1.5b-instruct-q4_k_m", admin_id="admin-1")


def test_verify_model_matches_after_install(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, _ = _install_fake_model(settings, service)
    result = service.verify_model(model_id, admin_id="admin-1")
    assert result["matches"] is True


def test_verify_model_detects_missing_file(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, installation = _install_fake_model(settings, service)
    Path(installation["install_path"]).unlink()
    result = service.verify_model(model_id, admin_id="admin-1")
    assert result["matches"] is False


# -- install_model ---------------------------------------------------------------------------


def test_install_model_creates_new_row(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, installation = _install_fake_model(settings, service)
    assert installation["status"] == "installed"
    assert installation["model_name"] == model_id


def test_install_model_updates_existing_row(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, first = _install_fake_model(settings, service)
    second = service.install_model(model_id, file_path=first["install_path"], admin_id="admin-1")
    assert first["public_id"] == second["public_id"]


def test_install_model_no_file_raises(service: RuntimeManagerService) -> None:
    with pytest.raises(ValidationError):
        service.install_model("qwen2.5-1.5b-instruct-q4_k_m", file_path="/totally/nonexistent/x.gguf", admin_id="admin-1")


def test_install_model_checksum_mismatch_marks_failed(settings: Settings, service: RuntimeManagerService) -> None:
    model_file = settings.resolved_allowed_model_dir / "test.gguf"
    model_file.write_bytes(b"real content")
    result = service.install_model(
        "qwen2.5-1.5b-instruct-q4_k_m", file_path=str(model_file), expected_sha256="0" * 64, admin_id="admin-1",
    )
    assert result["status"] == "failed"


# -- load_model -----------------------------------------------------------------------------


def test_load_model_not_installed_raises(service: RuntimeManagerService) -> None:
    with pytest.raises(ValidationError):
        service.load_model("qwen2.5-1.5b-instruct-q4_k_m", admin_id="admin-1")


def test_load_model_success(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, _ = _install_fake_model(settings, service)
    with patch("backend.services.runtime_manager_service.hardware_probe.probe", return_value=_FAKE_HARDWARE):
        runtime = service.load_model(model_id, admin_id="admin-1")
    assert runtime["loaded"] is True
    assert runtime["backend"] == "mock"


def test_load_model_updates_mb27_provider_config(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, installation = _install_fake_model(settings, service)
    with patch("backend.services.runtime_manager_service.hardware_probe.probe", return_value=_FAKE_HARDWARE):
        service.load_model(model_id, admin_id="admin-1")
    from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService

    items = MiniBrainProviderSettingsService(settings).list_settings(provider_type="local_model")["items"]
    assert items[0]["config"]["model_path"] == installation["install_path"]


def test_load_model_rejects_unsafe_ram(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, _ = _install_fake_model(settings, service, model_id="qwen2.5-3b-instruct-q4_k_m")
    with patch("backend.services.runtime_manager_service.hardware_probe.probe", return_value=_FAKE_HARDWARE):
        with pytest.raises(ValidationError):
            service.load_model(model_id, admin_id="admin-1")


# -- unload_model ---------------------------------------------------------------------------


def test_unload_model_when_nothing_loaded(service: RuntimeManagerService) -> None:
    result = service.unload_model(admin_id="admin-1")
    assert result["loaded"] is False


def test_unload_model_clears_provider_config(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, _ = _install_fake_model(settings, service)
    with patch("backend.services.runtime_manager_service.hardware_probe.probe", return_value=_FAKE_HARDWARE):
        service.load_model(model_id, admin_id="admin-1")
    service.unload_model(admin_id="admin-1")

    from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService

    items = MiniBrainProviderSettingsService(settings).list_settings(provider_type="local_model")["items"]
    assert items[0]["config"]["model_path"] is None


# -- benchmark_model ------------------------------------------------------------------------


def test_benchmark_model_not_installed_raises(service: RuntimeManagerService) -> None:
    with pytest.raises(ValidationError):
        service.benchmark_model("qwen2.5-1.5b-instruct-q4_k_m", admin_id="admin-1")


def test_benchmark_model_produces_rating(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, _ = _install_fake_model(settings, service)
    result = service.benchmark_model(model_id, admin_id="admin-1")
    assert result["rating"] in ("excellent", "good", "fair", "poor")
    assert result["tokens_per_second"] > 0
    assert result["peak_ram_mb"] > 0


def test_benchmark_model_persists_runtime_row(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, _ = _install_fake_model(settings, service)
    service.benchmark_model(model_id, admin_id="admin-1")
    with service.repository.transaction() as connection:
        rows = service.repository.list_runtime_history(connection, model_name=model_id)
    assert len(rows) >= 1


# -- remove_model ---------------------------------------------------------------------------


def test_remove_model_no_installation_raises(service: RuntimeManagerService) -> None:
    with pytest.raises(NotFoundError):
        service.remove_model("qwen2.5-1.5b-instruct-q4_k_m", admin_id="admin-1")


def test_remove_model_deletes_real_file(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, installation = _install_fake_model(settings, service)
    file_path = Path(installation["install_path"])
    assert file_path.exists()
    result = service.remove_model(model_id, admin_id="admin-1")
    assert result["status"] == "removed"
    assert not file_path.exists()


# -- runtime_status / auto_fallback_status ------------------------------------------------------


def test_runtime_status_reflects_installed_count(settings: Settings, service: RuntimeManagerService) -> None:
    _install_fake_model(settings, service)
    status = service.runtime_status()
    assert status["installed_count"] == 1


def test_auto_fallback_status_unavailable_when_nothing_configured(service: RuntimeManagerService) -> None:
    result = service.auto_fallback_status()
    assert result["step"] == 4
    assert result["backend"] == "unavailable"


def test_auto_fallback_status_installed_not_loaded(settings: Settings, service: RuntimeManagerService) -> None:
    _install_fake_model(settings, service)
    result = service.auto_fallback_status()
    assert result["step"] == 2
    assert result["backend"] == "local_installed"


def test_auto_fallback_status_loaded_takes_priority(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, _ = _install_fake_model(settings, service)
    with patch("backend.services.runtime_manager_service.hardware_probe.probe", return_value=_FAKE_HARDWARE):
        service.load_model(model_id, admin_id="admin-1")
    result = service.auto_fallback_status()
    assert result["step"] == 1
    assert result["backend"] == "local_loaded"


def test_auto_fallback_status_external_enabled(settings: Settings, service: RuntimeManagerService, monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService
    from core_model.mini_brain.provider_settings import secret_encryptor

    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, Fernet.generate_key().decode("ascii"))
    provider_service = MiniBrainProviderSettingsService(settings)
    setting = provider_service.create_provider_setting(provider_key="openai", enabled=True, config={}, admin_id="admin-1")
    provider_service.set_secret(setting["public_id"], secret_name="api_key", raw_value="sk-real-key", admin_id="admin-1")

    result = service.auto_fallback_status()
    assert result["step"] == 3
    assert result["backend"] == "external"


# -- events / memory / catalog ------------------------------------------------------------------


def test_list_events_after_install(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, _ = _install_fake_model(settings, service)
    events = service.list_events(model_name=model_id)["items"]
    assert any(event["event_type"] == "installed" for event in events)


def test_list_memory_after_install(settings: Settings, service: RuntimeManagerService) -> None:
    _install_fake_model(settings, service)
    memory = service.list_memory()["items"]
    assert any(row["event_type"] == "installed" for row in memory)


def test_catalog_returns_four_models(service: RuntimeManagerService) -> None:
    result = service.catalog()
    assert len(result["models"]) == 4


# -- diagnostics (post-audit remediation D1) ------------------------------------------------


def test_diagnostics_shape_when_nothing_configured(settings: Settings, service: RuntimeManagerService) -> None:
    result = service.diagnostics()
    for key in ("hardware", "model_status", "load_state", "benchmark_availability", "storage_paths", "fallback_state"):
        assert key in result
    assert result["load_state"]["loaded"] is False
    assert result["benchmark_availability"]["has_benchmark_data"] is False
    assert result["storage_paths"]["allowed_model_dir"] == str(settings.resolved_allowed_model_dir)
    assert result["fallback_state"]["backend"] == "unavailable"


def test_diagnostics_reflects_benchmark_data(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, _ = _install_fake_model(settings, service)
    service.benchmark_model(model_id, admin_id="admin-1")
    result = service.diagnostics()
    assert result["benchmark_availability"]["has_benchmark_data"] is True
    assert result["benchmark_availability"]["last_benchmark"]["tokens_per_second"] > 0


def test_diagnostics_reflects_loaded_model(settings: Settings, service: RuntimeManagerService) -> None:
    model_id, _ = _install_fake_model(settings, service)
    with patch("backend.services.runtime_manager_service.hardware_probe.probe", return_value=_FAKE_HARDWARE):
        service.load_model(model_id, admin_id="admin-1")
        result = service.diagnostics()
    assert result["load_state"]["loaded"] is True
    assert result["fallback_state"]["backend"] == "local_loaded"
