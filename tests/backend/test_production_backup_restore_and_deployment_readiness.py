import base64
import os
import shutil
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database, migration_status
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.database.schema import SCHEMA_VERSION
from backend.services.production_api_abuse_readiness_service import (
    ProductionApiAbuseReadinessService,
)
from backend.services.production_artifact_security_service import ProductionArtifactSecurityService
from backend.services.production_backup_restore_readiness_service import (
    ProductionBackupEncryptionAssessmentService,
    ProductionBackupEncryptionService,
    ProductionBackupReadinessService,
    ProductionRestoreReadinessService,
    encrypted_backup_paths,
)
from backend.services.production_deployment_readiness_service import (
    ProductionDeploymentReadinessService,
    ProductionSystemHealthService,
)
from backend.services.production_secret_scan_service import ProductionSecretScanService
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "db.sqlite",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _write_real_backup(
    settings: Settings, filename: str = "brud_ai_before_v37_20260101000000.db"
) -> Path:
    settings.resolved_backup_dir.mkdir(parents=True, exist_ok=True)
    target = settings.resolved_backup_dir / filename
    shutil.copy2(settings.resolved_database_path, target)
    return target


# -- backup readiness -------------------------------------------------------------------------


def test_check_backup_readiness_not_configured_when_no_backup(settings: Settings) -> None:
    service = ProductionBackupReadinessService(settings)
    result = service.check_backup_readiness(admin_id=ADMIN_ID)
    assert result["result_status"] == "not_configured"


def test_check_backup_readiness_passes_with_real_backup_file(settings: Settings) -> None:
    _write_real_backup(settings)
    service = ProductionBackupReadinessService(settings)
    result = service.check_backup_readiness(admin_id=ADMIN_ID)
    assert result["result_status"] in {"passed", "passed_with_warning"}, result
    assert result["latest_backup_filename"]


def test_check_backup_readiness_flags_stale_backup(settings: Settings) -> None:
    _write_real_backup(settings)
    service = ProductionBackupReadinessService(settings)
    result = service.check_backup_readiness(admin_id=ADMIN_ID, max_age_seconds=-1)
    assert result["result_status"] == "failed"


# -- backup encryption assessment (Phase 15A Step 14) -----------------------------------------


def test_assess_backup_encryption_not_configured_when_no_backup(settings: Settings) -> None:
    service = ProductionBackupEncryptionAssessmentService(settings)
    result = service.assess(admin_id=ADMIN_ID)
    assert result["result_status"] == "not_configured"
    assert "no_backup_present" in result["findings"]


def test_assess_backup_encryption_honestly_reports_not_encrypted_for_a_plain_backup(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(settings.backup_encryption_key_env_var, raising=False)
    _write_real_backup(settings)
    service = ProductionBackupEncryptionAssessmentService(settings)
    result = service.assess(admin_id=ADMIN_ID)
    assert result["result_status"] == "not_encrypted"
    assert "latest_backup_not_encrypted" in result["findings"]
    assert "no_encryption_key_present_in_environment" in result["findings"]
    assert result["checks"]["encryption_library_available"] is True
    assert result["checks"]["key_present_in_environment"] is False


def test_assess_backup_encryption_still_not_encrypted_when_only_the_key_is_present(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A key being available in the environment is necessary but not
    # sufficient -- the latest backup itself must actually have an
    # encrypted sidecar, or this must still honestly report not_encrypted
    # rather than treating "a key exists somewhere" as proof of encryption.
    monkeypatch.setenv(settings.backup_encryption_key_env_var, "not-a-real-key-just-a-test-value")
    _write_real_backup(settings)
    service = ProductionBackupEncryptionAssessmentService(settings)
    result = service.assess(admin_id=ADMIN_ID)
    assert result["result_status"] == "not_encrypted"
    assert "latest_backup_not_encrypted" in result["findings"]


def test_assess_backup_encryption_reports_encrypted_when_sidecar_and_key_both_present(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, "not-a-real-key-just-a-test-value")
    backup_path = _write_real_backup(settings)
    _, meta_path = encrypted_backup_paths(settings.resolved_backup_dir, backup_path.name)
    meta_path.write_text("{}", encoding="utf-8")

    service = ProductionBackupEncryptionAssessmentService(settings)
    result = service.assess(admin_id=ADMIN_ID)
    assert result["result_status"] == "encrypted"
    assert result["findings"] == []


def test_assess_backup_encryption_never_exposes_the_key_value_itself(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_key_value = "super-secret-key-value-must-never-appear-anywhere"
    monkeypatch.setenv(settings.backup_encryption_key_env_var, secret_key_value)
    _write_real_backup(settings)
    service = ProductionBackupEncryptionAssessmentService(settings)
    result = service.assess(admin_id=ADMIN_ID)

    import json
    serialized = json.dumps(result, default=str)
    assert secret_key_value not in serialized
    # The event persisted to the database must not carry it either.
    assert secret_key_value not in json.dumps(result["event"], default=str)


# -- governed backup encryption (Phase 15A Steps 15-16) -----------------------------------------


def _valid_key_b64() -> str:
    return base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


def test_encrypt_latest_backup_fails_closed_when_no_backup_present(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    service = ProductionBackupEncryptionService(settings)
    with pytest.raises(ValidationError, match="no backup is present"):
        service.encrypt_latest_backup(admin_id=ADMIN_ID)


def test_encrypt_latest_backup_fails_closed_when_key_is_missing(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(settings.backup_encryption_key_env_var, raising=False)
    _write_real_backup(settings)
    service = ProductionBackupEncryptionService(settings)
    with pytest.raises(ValidationError, match="not present"):
        service.encrypt_latest_backup(admin_id=ADMIN_ID)


def test_encrypt_latest_backup_fails_closed_when_key_is_the_wrong_length(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        settings.backup_encryption_key_env_var,
        base64.urlsafe_b64encode(b"too-short").decode("ascii"),
    )
    _write_real_backup(settings)
    service = ProductionBackupEncryptionService(settings)
    with pytest.raises(ValidationError, match="32-byte"):
        service.encrypt_latest_backup(admin_id=ADMIN_ID)


def test_encrypt_latest_backup_produces_a_real_encrypted_sidecar_and_updates_the_assessment(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    backup_path = _write_real_backup(settings)
    plaintext = backup_path.read_bytes()

    service = ProductionBackupEncryptionService(settings)
    result = service.encrypt_latest_backup(admin_id=ADMIN_ID)
    assert result["result_status"] == "encrypted"

    encrypted_path, meta_path = encrypted_backup_paths(
        settings.resolved_backup_dir, backup_path.name
    )
    assert encrypted_path.exists()
    assert meta_path.exists()
    # The ciphertext is not the plaintext, and the sidecar carries no key material.
    assert encrypted_path.read_bytes() != plaintext
    meta_text = meta_path.read_text(encoding="utf-8")
    assert os.environ[settings.backup_encryption_key_env_var] not in meta_text

    assessment = ProductionBackupEncryptionAssessmentService(settings).assess(admin_id=ADMIN_ID)
    assert assessment["result_status"] == "encrypted"


def test_decrypt_backup_round_trips_to_the_exact_original_bytes(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    backup_path = _write_real_backup(settings)
    plaintext_before = backup_path.read_bytes()

    service = ProductionBackupEncryptionService(settings)
    service.encrypt_latest_backup(admin_id=ADMIN_ID)
    decrypted, meta = service.decrypt_backup(settings.resolved_backup_dir, backup_path.name)
    assert decrypted == plaintext_before
    assert meta["algorithm"] == "AES-256-GCM"
    assert meta["key_reference"] == settings.backup_encryption_key_env_var


def test_decrypt_backup_fails_closed_with_the_wrong_key(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    backup_path = _write_real_backup(settings)
    service = ProductionBackupEncryptionService(settings)
    service.encrypt_latest_backup(admin_id=ADMIN_ID)

    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    with pytest.raises(ValidationError, match="wrong key or corrupted"):
        service.decrypt_backup(settings.resolved_backup_dir, backup_path.name)


def test_encrypt_latest_backup_rejects_concurrent_execution_on_same_backup_dir(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading
    import time

    import backend.services.production_backup_restore_readiness_service as backup_service_module

    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    _write_real_backup(settings)

    original_load_key = backup_service_module._load_encryption_key

    def _slow_load_key(settings_arg):
        time.sleep(0.5)
        return original_load_key(settings_arg)

    monkeypatch.setattr(backup_service_module, "_load_encryption_key", _slow_load_key)
    service = ProductionBackupEncryptionService(settings)

    thread = threading.Thread(target=lambda: service.encrypt_latest_backup(admin_id=ADMIN_ID))
    thread.start()
    try:
        time.sleep(0.1)
        with pytest.raises(ValidationError, match="only one may run at a time"):
            service.encrypt_latest_backup(admin_id=ADMIN_ID)
    finally:
        thread.join()


def test_decrypt_backup_fails_closed_with_corrupted_ciphertext(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    backup_path = _write_real_backup(settings)
    service = ProductionBackupEncryptionService(settings)
    service.encrypt_latest_backup(admin_id=ADMIN_ID)

    encrypted_path, _ = encrypted_backup_paths(settings.resolved_backup_dir, backup_path.name)
    corrupted = bytearray(encrypted_path.read_bytes())
    corrupted[0] ^= 0xFF
    encrypted_path.write_bytes(bytes(corrupted))

    with pytest.raises(ValidationError, match="checksum mismatch"):
        service.decrypt_backup(settings.resolved_backup_dir, backup_path.name)


# -- isolated encrypted-restore verification (Phase 15A Steps 17-18) ----------------------------


def test_verify_encrypted_restore_not_configured_when_no_backup(settings: Settings) -> None:
    service = ProductionBackupEncryptionService(settings)
    result = service.verify_encrypted_restore(admin_id=ADMIN_ID)
    assert result["result_status"] == "not_configured"
    assert "no_backup_present" in result["findings"]


def test_verify_encrypted_restore_not_configured_when_backup_is_not_encrypted(
    settings: Settings,
) -> None:
    _write_real_backup(settings)
    service = ProductionBackupEncryptionService(settings)
    result = service.verify_encrypted_restore(admin_id=ADMIN_ID)
    assert result["result_status"] == "not_configured"
    assert "latest_backup_not_encrypted" in result["findings"]


def test_verify_encrypted_restore_passes_for_a_real_encrypted_backup(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    _write_real_backup(settings)
    service = ProductionBackupEncryptionService(settings)
    service.encrypt_latest_backup(admin_id=ADMIN_ID)

    result = service.verify_encrypted_restore(admin_id=ADMIN_ID)
    assert result["result_status"] == "passed", result["details"]
    assert result["details"]["integrity_check"] == "ok"
    assert result["details"]["schema_version"] == SCHEMA_VERSION
    assert result["findings"] == []


def test_verify_encrypted_restore_never_replaces_the_live_database_file(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The live database is legitimately written to by this call (it
    # records its own readiness event, exactly like every other Phase 15
    # readiness check already does) -- that is not a "restore" and not
    # what this test guards against. What must never happen is the live
    # database *file itself* being deleted/replaced with restored
    # content, so this asserts the file at that path is still the same
    # inode (proxy: real restores replace the file, they don't append
    # rows to it) and is still a healthy, schema-38 database afterward.
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    _write_real_backup(settings)
    service = ProductionBackupEncryptionService(settings)
    service.encrypt_latest_backup(admin_id=ADMIN_ID)

    inode_before = settings.resolved_database_path.stat().st_ino
    service.verify_encrypted_restore(admin_id=ADMIN_ID)
    assert settings.resolved_database_path.stat().st_ino == inode_before
    assert migration_status(settings.resolved_database_path)["current_version"] == SCHEMA_VERSION


def test_verify_encrypted_restore_leaves_no_decrypted_plaintext_behind(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The drill's temp directory is created with a distinctive prefix and
    # must not survive the call -- this is the concrete, checkable proxy
    # for "the isolated temp directory, including the decrypted
    # plaintext, is deleted regardless of outcome."
    import glob
    import tempfile as tempfile_module

    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    _write_real_backup(settings)
    service = ProductionBackupEncryptionService(settings)
    service.encrypt_latest_backup(admin_id=ADMIN_ID)
    service.verify_encrypted_restore(admin_id=ADMIN_ID)

    leftovers = glob.glob(
        f"{tempfile_module.gettempdir()}/brud_encrypted_restore_drill_*"
    )
    assert leftovers == []


def test_verify_encrypted_restore_is_blocked_with_the_wrong_key(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    _write_real_backup(settings)
    service = ProductionBackupEncryptionService(settings)
    service.encrypt_latest_backup(admin_id=ADMIN_ID)

    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    result = service.verify_encrypted_restore(admin_id=ADMIN_ID)
    assert result["result_status"] == "blocked"
    assert any("decrypt_failed" in finding for finding in result["findings"])


def test_verify_encrypted_restore_is_blocked_for_corrupted_ciphertext(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    backup_path = _write_real_backup(settings)
    service = ProductionBackupEncryptionService(settings)
    service.encrypt_latest_backup(admin_id=ADMIN_ID)

    encrypted_path, _ = encrypted_backup_paths(settings.resolved_backup_dir, backup_path.name)
    corrupted = bytearray(encrypted_path.read_bytes())
    corrupted[0] ^= 0xFF
    encrypted_path.write_bytes(bytes(corrupted))

    result = service.verify_encrypted_restore(admin_id=ADMIN_ID)
    assert result["result_status"] == "blocked"
    assert any("decrypt_failed" in finding for finding in result["findings"])


# -- overview counter (Phase 15A Step 31) --------------------------------------------------------


def test_overview_backups_not_encrypted_zero_when_never_assessed(settings: Settings) -> None:
    # Absence of evidence is already surfaced (blocking) by deployment
    # readiness -- this quick-glance overview counter should stay 0
    # rather than nagging about something never even checked.
    repository = ProductionReadinessRepository(settings.resolved_database_path)
    assert repository.overview_counts()["backups_not_encrypted"] == 0


def test_overview_backups_not_encrypted_one_when_latest_assessment_is_not_encrypted(
    settings: Settings,
) -> None:
    _write_real_backup(settings)
    ProductionBackupEncryptionAssessmentService(settings).assess(admin_id=ADMIN_ID)

    repository = ProductionReadinessRepository(settings.resolved_database_path)
    assert repository.overview_counts()["backups_not_encrypted"] == 1


def test_overview_backups_not_encrypted_zero_once_actually_encrypted(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    _write_real_backup(settings)
    ProductionBackupEncryptionAssessmentService(settings).assess(admin_id=ADMIN_ID)
    ProductionBackupEncryptionService(settings).encrypt_latest_backup(admin_id=ADMIN_ID)
    ProductionBackupEncryptionAssessmentService(settings).assess(admin_id=ADMIN_ID)

    repository = ProductionReadinessRepository(settings.resolved_database_path)
    assert repository.overview_counts()["backups_not_encrypted"] == 0


# -- restore readiness ------------------------------------------------------------------------


def test_check_restore_readiness_not_configured_when_no_backup(settings: Settings) -> None:
    service = ProductionRestoreReadinessService(settings)
    result = service.check_restore_readiness(admin_id=ADMIN_ID)
    assert result["result_status"] == "not_configured"


def test_check_restore_readiness_passes_for_real_backup_copy(settings: Settings) -> None:
    _write_real_backup(settings)
    service = ProductionRestoreReadinessService(settings)
    result = service.check_restore_readiness(admin_id=ADMIN_ID)
    assert result["result_status"] == "passed", result["details"]
    assert result["details"]["integrity_check"] == "ok"
    assert result["details"]["schema_version"] == SCHEMA_VERSION


def test_check_restore_readiness_fails_for_corrupt_backup(settings: Settings) -> None:
    settings.resolved_backup_dir.mkdir(parents=True, exist_ok=True)
    corrupt = settings.resolved_backup_dir / "brud_ai_before_v37_20260101000000.db"
    corrupt.write_bytes(b"not a real sqlite database")
    service = ProductionRestoreReadinessService(settings)
    result = service.check_restore_readiness(admin_id=ADMIN_ID)
    assert result["result_status"] == "failed"
    assert result["details"]["findings"]


# -- deployment readiness ---------------------------------------------------------------------


def test_deployment_readiness_not_ready_when_nothing_assessed(settings: Settings) -> None:
    service = ProductionDeploymentReadinessService(settings)
    result = service.assess(admin_id=ADMIN_ID)
    assert result["result_status"] == "not_ready"
    assert all(reason.endswith("_never_assessed") for reason in result["blocking_reasons"])


def test_deployment_readiness_ready_when_all_checks_pass(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(settings.backup_encryption_key_env_var, _valid_key_b64())
    _write_real_backup(settings)
    ProductionBackupReadinessService(settings).check_backup_readiness(admin_id=ADMIN_ID)
    ProductionRestoreReadinessService(settings).check_restore_readiness(admin_id=ADMIN_ID)
    ProductionApiAbuseReadinessService(settings).assess(admin_id=ADMIN_ID)
    ProductionSecretScanService(settings).verify_redaction_mechanism(admin_id=ADMIN_ID)

    artifact_service = ProductionArtifactSecurityService(settings)
    artifact_service.check_backup_artifact(admin_id=ADMIN_ID)

    # Phase 15A Step 22 additions: canonical regression, browser
    # verification, and backup encryption evidence. Canonical
    # regression/browser-e2e evidence is recorded at the repository layer
    # directly (as a completed real run would have left it) rather than
    # actually running the full manifest or a real Playwright suite here
    # -- this test exercises the deployment-readiness *read* side, which
    # is exactly the layer it reads from either way.
    repository = ProductionReadinessRepository(settings.resolved_database_path)
    run = repository.create_regression_run(
        {
            "run_code": "REG-test0000000000000001",
            "batch_plan": [{"manifest_version": 1, "batch_ids": ["browser_e2e_01"]}],
            "created_by_admin_public_id": ADMIN_ID,
        }
    )
    repository.add_regression_result(
        run["public_id"],
        {
            "batch_name": "browser_e2e:browser_e2e_01", "command": "npx playwright test",
            "status": "passed", "passed_count": 41, "failed_count": 0, "error_count": 0,
        },
    )
    repository.record_readiness_event(
        {
            "event_type": "canonical_regression_finalized",
            "resource_type": "production_regression_run",
            "resource_public_id": run["public_id"],
            "summary": "result_status=passed",
            "metadata": {},
            "performed_by_admin_public_id": ADMIN_ID,
        }
    )
    ProductionBackupEncryptionService(settings).encrypt_latest_backup(admin_id=ADMIN_ID)
    ProductionBackupEncryptionAssessmentService(settings).assess(admin_id=ADMIN_ID)

    service = ProductionDeploymentReadinessService(settings)
    result = service.assess(admin_id=ADMIN_ID)
    assert result["result_status"] == "ready", result["blocking_reasons"]
    assert result["blocking_reasons"] == []
    assert result["checks"]["canonical_regression"] == "passed"
    assert result["checks"]["browser_verification"] == "passed"
    assert result["checks"]["backup_encryption"] == "encrypted"


def test_deployment_readiness_blocks_on_never_assessed_step22_checks_alone(
    settings: Settings,
) -> None:
    # Confirms the three new checks are genuinely load-bearing, not
    # decorative: with every *other* check passing, missing evidence for
    # just these three must still block readiness.
    _write_real_backup(settings)
    ProductionBackupReadinessService(settings).check_backup_readiness(admin_id=ADMIN_ID)
    ProductionRestoreReadinessService(settings).check_restore_readiness(admin_id=ADMIN_ID)
    ProductionApiAbuseReadinessService(settings).assess(admin_id=ADMIN_ID)
    ProductionSecretScanService(settings).verify_redaction_mechanism(admin_id=ADMIN_ID)
    ProductionArtifactSecurityService(settings).check_backup_artifact(admin_id=ADMIN_ID)

    result = ProductionDeploymentReadinessService(settings).assess(admin_id=ADMIN_ID)
    assert result["result_status"] == "not_ready"
    assert set(result["blocking_reasons"]) == {
        "canonical_regression_never_assessed",
        "browser_verification_never_assessed",
        "backup_encryption_never_assessed",
    }


def test_deployment_readiness_blocked_when_backup_is_not_yet_encrypted(
    settings: Settings,
) -> None:
    _write_real_backup(settings)
    ProductionBackupReadinessService(settings).check_backup_readiness(admin_id=ADMIN_ID)
    ProductionRestoreReadinessService(settings).check_restore_readiness(admin_id=ADMIN_ID)
    ProductionApiAbuseReadinessService(settings).assess(admin_id=ADMIN_ID)
    ProductionSecretScanService(settings).verify_redaction_mechanism(admin_id=ADMIN_ID)
    ProductionArtifactSecurityService(settings).check_backup_artifact(admin_id=ADMIN_ID)
    # An honest not_encrypted assessment was run -- but that is still not
    # enough to satisfy the deployment gate.
    ProductionBackupEncryptionAssessmentService(settings).assess(admin_id=ADMIN_ID)

    result = ProductionDeploymentReadinessService(settings).assess(admin_id=ADMIN_ID)
    assert result["checks"]["backup_encryption"] == "not_encrypted"
    assert "backup_encryption_not_encrypted" in result["blocking_reasons"]
    assert result["result_status"] == "blocked"


# -- system health -----------------------------------------------------------------------------


def test_system_health_snapshot_reports_healthy_database(settings: Settings) -> None:
    service = ProductionSystemHealthService(settings)
    result = service.snapshot(admin_id=ADMIN_ID)
    assert result["overall_status"] == "healthy"
    assert result["database"]["integrity"] == "ok"
    assert result["database"]["schema_version"] == SCHEMA_VERSION
