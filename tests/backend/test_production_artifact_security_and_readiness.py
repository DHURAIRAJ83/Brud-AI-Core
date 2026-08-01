import base64
import os
import shutil
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.services.production_api_abuse_readiness_service import (
    ProductionApiAbuseReadinessService,
)
from backend.services.production_artifact_security_service import ProductionArtifactSecurityService
from backend.services.production_backup_restore_readiness_service import (
    ProductionBackupEncryptionService,
    ProductionBackupReadinessService,
)
from backend.services.production_secret_scan_service import ProductionSecretScanService
from tests.backend.test_production_model_release_validation_activation import (
    _validated_release_request,
)
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "production_artifact_security.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        tokenizer_corpus_dir=tmp_path / "tokenizer_corpus",
        tokenizer_dir=tmp_path / "tokenizers",
        core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        release_artifact_dir=tmp_path / "release_artifacts",
        release_bundle_dir=tmp_path / "release_bundles",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


# -- artifact security -----------------------------------------------------------------------


def test_check_release_candidate_artifacts_passes_for_real_artifacts(settings: Settings) -> None:
    validated = _validated_release_request(settings)
    service = ProductionArtifactSecurityService(settings)
    results = service.check_release_candidate_artifacts(
        validated["model_release_candidate_public_id"], admin_id=ADMIN_ID,
    )
    assert results, "expected at least one collected artifact to check"
    assert all(r["result_status"] in {"passed", "passed_with_warning"} for r in results), results
    checkpoint_checks = [r for r in results if r["artifact_type"] == "checkpoint"]
    assert checkpoint_checks and checkpoint_checks[0]["result_status"] == "passed"


def test_check_release_candidate_artifacts_detects_checksum_tampering(settings: Settings) -> None:
    validated = _validated_release_request(settings)
    repository = ProductionReadinessRepository(settings.resolved_database_path)
    candidate_public_id = validated["model_release_candidate_public_id"]

    tampered_path = (
        settings.resolved_release_artifact_dir / candidate_public_id / "model_config.json"
    )
    assert tampered_path.exists()
    tampered_path.write_text('{"tampered": true}', encoding="utf-8")

    service = ProductionArtifactSecurityService(settings)
    results = service.check_release_candidate_artifacts(candidate_public_id, admin_id=ADMIN_ID)
    config_checks = [
        r for r in results
        if r["artifact_type"] == "configuration" and "checksum_mismatch" in r["findings"]
    ]
    assert config_checks, results
    assert config_checks[0]["result_status"] == "failed"

    stored = repository.list_artifact_security_checks(artifact_type="configuration")
    assert any("checksum_mismatch" in row["findings"] for row in stored)


def test_check_backup_artifact_not_configured_when_no_backup(settings: Settings) -> None:
    service = ProductionArtifactSecurityService(settings)
    result = service.check_backup_artifact(admin_id=ADMIN_ID)
    assert result["result_status"] == "not_configured"
    assert "no_backup_present" in result["findings"]


def _write_real_backup(settings: Settings) -> Path:
    settings.resolved_backup_dir.mkdir(parents=True, exist_ok=True)
    target = settings.resolved_backup_dir / "brud_ai_before_v38_20260101000000.db"
    shutil.copy2(settings.resolved_database_path, target)
    return target


def test_check_backup_artifact_reports_no_encrypted_sidecar_for_a_plain_backup(
    settings: Settings,
) -> None:
    _write_real_backup(settings)
    service = ProductionArtifactSecurityService(settings)
    result = service.check_backup_artifact(admin_id=ADMIN_ID)
    # Informational only -- a plaintext backup with no encrypted sidecar
    # still passes this check; encryption readiness is a separate,
    # dedicated assessment (Phase 15A Step 14).
    assert result["result_status"] == "passed"
    assert result["checks"]["encrypted_sidecar_present"] is False


def test_check_backup_artifact_reports_encrypted_sidecar_when_present(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        settings.backup_encryption_key_env_var,
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
    )
    _write_real_backup(settings)
    ProductionBackupEncryptionService(settings).encrypt_latest_backup(admin_id=ADMIN_ID)

    result = ProductionArtifactSecurityService(settings).check_backup_artifact(admin_id=ADMIN_ID)
    assert result["result_status"] == "passed"
    assert result["checks"]["encrypted_sidecar_present"] is True


def test_backup_age_readiness_is_unaffected_by_encrypting_the_backup(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Encrypting produces a sibling `.enc` file -- it must never replace
    # or move the original plaintext backup that age/staleness checks
    # depend on.
    monkeypatch.setenv(
        settings.backup_encryption_key_env_var,
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
    )
    _write_real_backup(settings)
    before = ProductionBackupReadinessService(settings).check_backup_readiness(admin_id=ADMIN_ID)
    assert before["result_status"] in {"passed", "passed_with_warning"}

    ProductionBackupEncryptionService(settings).encrypt_latest_backup(admin_id=ADMIN_ID)

    after = ProductionBackupReadinessService(settings).check_backup_readiness(admin_id=ADMIN_ID)
    assert after["result_status"] == before["result_status"]
    assert after["latest_backup_filename"] == before["latest_backup_filename"]


# -- API abuse readiness ----------------------------------------------------------------------


def test_api_abuse_readiness_assess_passes(settings: Settings) -> None:
    service = ProductionApiAbuseReadinessService(settings)
    result = service.assess(admin_id=ADMIN_ID)
    assert result["result_status"] == "passed", result["findings"]
    assert result["checks"]["chat_message_length_bounded"] is True
    assert result["checks"]["csrf_configured"] is True
    assert result["checks"]["canary_thresholds_bounded"] is True
    assert result["checks"]["no_forbidden_download_endpoints"] is True


# -- secret scan -------------------------------------------------------------------------------


def test_secret_scan_redaction_mechanism_passes(settings: Settings) -> None:
    service = ProductionSecretScanService(settings)
    result = service.verify_redaction_mechanism(admin_id=ADMIN_ID)
    assert result["result_status"] == "passed", result["findings"]


def test_secret_scan_frontend_bundle_not_applicable_when_no_build(
    settings: Settings, tmp_path: Path
) -> None:
    service = ProductionSecretScanService(settings)
    result = service.scan_frontend_bundle(admin_id=ADMIN_ID, build_dir=tmp_path / "no-such-dist")
    assert result["result_status"] == "not_applicable"


def test_secret_scan_frontend_bundle_detects_leaked_key(settings: Settings, tmp_path: Path) -> None:
    build_dir = tmp_path / "dist"
    build_dir.mkdir()
    (build_dir / "main.js").write_text(
        'const key = "sk-abcdefghijklmnopqrstuvwxyz123456";', encoding="utf-8",
    )
    service = ProductionSecretScanService(settings)
    result = service.scan_frontend_bundle(admin_id=ADMIN_ID, build_dir=build_dir)
    assert result["result_status"] == "failed"
    assert result["findings"]
    assert result["scanned_files"] == 1


def test_secret_scan_domain_model_field_names_runs(settings: Settings) -> None:
    service = ProductionSecretScanService(settings)
    result = service.scan_domain_model_field_names(admin_id=ADMIN_ID)
    assert result["result_status"] in {"passed", "passed_with_warning"}
    assert all("token" not in f.split("'")[1].lower() for f in result["findings"] if "'" in f)


def test_secret_scan_backup_sidecar_files_passes_with_no_backups(settings: Settings) -> None:
    result = ProductionSecretScanService(settings).scan_backup_sidecar_files(admin_id=ADMIN_ID)
    assert result["result_status"] == "passed"
    assert result["scanned_files"] == 0


def test_secret_scan_backup_sidecar_files_passes_for_a_real_encrypted_backup(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        settings.backup_encryption_key_env_var,
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
    )
    _write_real_backup(settings)
    ProductionBackupEncryptionService(settings).encrypt_latest_backup(admin_id=ADMIN_ID)

    result = ProductionSecretScanService(settings).scan_backup_sidecar_files(admin_id=ADMIN_ID)
    assert result["result_status"] == "passed", result["findings"]
    assert result["scanned_files"] == 1


def test_secret_scan_backup_sidecar_files_detects_a_leaked_secret_shaped_value(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Simulates a hypothetical future bug that wrote a secret-shaped value
    # into the sidecar -- this scan must catch it independently of
    # whether the writing code intended to.
    monkeypatch.setenv(
        settings.backup_encryption_key_env_var,
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
    )
    _write_real_backup(settings)
    ProductionBackupEncryptionService(settings).encrypt_latest_backup(admin_id=ADMIN_ID)

    sidecar = next(settings.resolved_backup_dir.glob("*.enc.meta.json"))
    sidecar.write_text(
        sidecar.read_text(encoding="utf-8")[:-1]
        + ', "leaked": "sk-abcdefghijklmnopqrstuvwxyz123456"}',
        encoding="utf-8",
    )

    result = ProductionSecretScanService(settings).scan_backup_sidecar_files(admin_id=ADMIN_ID)
    assert result["result_status"] == "failed"
    assert result["findings"]
