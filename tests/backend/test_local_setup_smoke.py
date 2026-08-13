"""MB-29: real end-to-end smoke test for Local Model Auto-Setup &
Provider Configuration Center.

Drives the exact 10-step scenario the phase spec's own section 11
lists, against a real `LocalSetupService` backed by a real temporary
database and a real, temporary allowed model directory -- no mocking
anywhere in this file. Confirms MB-27's own `MiniBrainProviderSettingsService`
is the thing that actually persisted the saved configuration (not a
bespoke MB-29 table), and that no plaintext secret ever appears in any
response this service returns.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.local_setup_service import LocalSetupService
from backend.services.mini_brain_provider_settings_service import MiniBrainProviderSettingsService
from core_model.mini_brain.provider_settings import secret_encryptor

FAKE_API_KEY = "sk-or-v1-fake-smoke-test-key-never-real-0123456789"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # -- step 1: create a temporary allowed model directory ----------------------------------
    allowed_model_dir = tmp_path / "models"
    allowed_model_dir.mkdir()
    result = Settings(
        database_path=tmp_path / "api.db", database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path, document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports", allowed_model_dir=allowed_model_dir,
        allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(result.resolved_database_path)
    return result


def test_mb29_end_to_end_smoke(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, Fernet.generate_key().decode("ascii"))

    service = LocalSetupService(settings)

    # -- step 2: create a fake GGUF file ------------------------------------------------------
    model_file = settings.resolved_allowed_model_dir / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    model_file.write_bytes(b"fake-gguf-bytes-for-smoke-test")

    # -- step 3: run hardware probe -----------------------------------------------------------
    hardware = service.hardware_summary()
    assert hardware["total_ram_gb"] >= 0
    assert hardware["recommended_ram_tier"] in ("4GB", "6GB", "8GB", "16GB", "32GB+")
    assert hardware["health"]["health"] == "unconfigured"  # nothing saved yet

    # -- step 4: scan models -------------------------------------------------------------------
    scan = service.scan_local_models()
    assert len(scan["items"]) == 1
    assert scan["items"][0]["filename"] == "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    assert scan["items"][0]["inferred_family"] == "qwen2.5"

    # -- step 5: get recommendations ------------------------------------------------------------
    recommendations = service.recommend_models()
    assert recommendations["top_recommendation"] is not None
    assert len(recommendations["models"]) >= 1

    # -- step 6: save local model config ---------------------------------------------------------
    saved = service.save_local_model_configuration(
        model_path=str(model_file), context_length=2048, max_tokens=512, temperature=0.3, threads=4,
        admin_id="admin-1",
    )
    assert saved["provider_key"] == "local_llm"
    assert saved["config"]["model_path"] == str(model_file)
    assert saved["config"]["context_length"] == 2048

    # -- step 7: verify MB-27 provider setting was actually updated ------------------------------
    provider_service = MiniBrainProviderSettingsService(settings)
    fetched = provider_service.get_setting(saved["public_id"])
    assert fetched["provider_key"] == "local_llm"
    assert fetched["config"]["model_path"] == str(model_file)
    assert fetched["config"]["threads"] == 4

    # -- step 8: build setup guide -----------------------------------------------------------------
    guide = service.build_setup_guide()
    assert len(guide["steps"]) >= 3
    assert any("saved" in step["body_en"].lower() or "configuration" in step["title_en"].lower() for step in guide["steps"])

    # -- step 9: ensure no plaintext secret leaked anywhere -------------------------------------------
    external = service.save_external_provider_configuration(
        provider_key="openai", api_key=FAKE_API_KEY, model="gpt-4o-mini", enabled=True, admin_id="admin-1",
    )
    assert FAKE_API_KEY not in str(external)
    assert FAKE_API_KEY not in str(saved)
    assert FAKE_API_KEY not in str(guide)
    diagnostics_before_secret_check = service.diagnostics()
    assert FAKE_API_KEY not in str(diagnostics_before_secret_check)

    # -- step 10: ensure diagnostics reports the selected model -------------------------------------
    diagnostics = service.diagnostics()
    assert diagnostics["configured_model_path"] == "qwen2.5-1.5b-instruct-q4_k_m.gguf"  # masked to filename only
    assert diagnostics["local_model_available"] is True
    assert diagnostics["scanned_model_count"] == 1
    assert "openai" in diagnostics["configured_external_providers"]
    assert str(model_file) not in str(diagnostics)  # never a raw absolute path
