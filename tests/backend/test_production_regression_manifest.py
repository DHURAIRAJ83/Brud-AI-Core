import copy
import json
import threading
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.services.production_regression_service import (
    REQUIRED_MANIFEST_CATEGORIES,
    ProductionRegressionService,
    compute_manifest_checksum,
    validate_manifest_schema,
)
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID

_REAL_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "production_regression_manifest.json"
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "regression_manifest.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _real_manifest() -> dict:
    return json.loads(_REAL_MANIFEST_PATH.read_text(encoding="utf-8"))


def _write_manifest(path: Path, manifest: dict) -> None:
    path.write_text(json.dumps(manifest), encoding="utf-8")


def _tiny_valid_manifest() -> dict:
    manifest = {
        "manifest_version": 1,
        "name": "tiny",
        "description": "tiny test manifest",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "required_environment": {},
        "batches": [
            {
                "batch_id": f"{category}_01",
                "title": category,
                "category": category,
                "working_directory": ".",
                "command": ["${PYTHON}", "--version"],
                "timeout_seconds": 10,
                "required": True,
                "retry_policy": {"max_retries": 0, "retry_on": []},
                "expected_artifacts": [],
                "failure_classification_rules": {
                    "passed_if_exit_code_in": [0],
                    "environment_failed_if_exit_code_in": [124, 137],
                },
            }
            for category in sorted(REQUIRED_MANIFEST_CATEGORIES)
        ],
        "finalization_policy": {},
    }
    manifest["manifest_checksum_sha256"] = compute_manifest_checksum(manifest)
    return manifest


# -- manifest loading / schema validation -------------------------------------------------------


def test_real_manifest_loads_and_validates(settings: Settings) -> None:
    service = ProductionRegressionService(settings)
    manifest = service.load_manifest()
    assert manifest["manifest_version"] >= 2
    assert len(manifest["batches"]) >= len(REQUIRED_MANIFEST_CATEGORIES)


def test_real_manifest_covers_every_required_category() -> None:
    manifest = _real_manifest()
    categories = {b["category"] for b in manifest["batches"]}
    assert REQUIRED_MANIFEST_CATEGORIES <= categories


def test_valid_tiny_manifest_passes_schema_validation() -> None:
    assert validate_manifest_schema(_tiny_valid_manifest()) == []


def test_schema_validation_rejects_missing_top_level_key() -> None:
    manifest = _tiny_valid_manifest()
    del manifest["finalization_policy"]
    problems = validate_manifest_schema(manifest)
    assert any("finalization_policy" in p for p in problems)


def test_schema_validation_rejects_duplicate_batch_id() -> None:
    manifest = _tiny_valid_manifest()
    manifest["batches"].append(copy.deepcopy(manifest["batches"][0]))
    problems = validate_manifest_schema(manifest)
    assert any("duplicate batch_id" in p for p in problems)


def test_schema_validation_rejects_unknown_category() -> None:
    manifest = _tiny_valid_manifest()
    manifest["batches"][0]["category"] = "not_a_real_category"
    problems = validate_manifest_schema(manifest)
    assert any("unknown category" in p for p in problems)


def test_schema_validation_rejects_missing_required_category() -> None:
    manifest = _tiny_valid_manifest()
    manifest["batches"] = [
        b for b in manifest["batches"] if b["category"] != "browser_e2e"
    ]
    problems = validate_manifest_schema(manifest)
    assert any("missing required categories" in p for p in problems)


def test_load_manifest_rejects_modified_manifest(settings: Settings, tmp_path: Path) -> None:
    manifest = _tiny_valid_manifest()
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, manifest)

    # Tamper with a field after the checksum was computed.
    tampered = json.loads(manifest_path.read_text())
    tampered["description"] = "an attacker changed this after the checksum was computed"
    _write_manifest(manifest_path, tampered)

    service = ProductionRegressionService(settings, manifest_path=manifest_path)
    with pytest.raises(ValidationError, match="checksum mismatch"):
        service.load_manifest()


def test_load_manifest_missing_file_raises_not_found(settings: Settings, tmp_path: Path) -> None:
    service = ProductionRegressionService(settings, manifest_path=tmp_path / "does_not_exist.json")
    with pytest.raises(NotFoundError):
        service.load_manifest()


# -- run creation / execution / finalization -----------------------------------------------------


def test_create_manifest_run_binds_checksum_and_batch_ids(settings: Settings) -> None:
    service = ProductionRegressionService(settings)
    run = service.create_manifest_run(admin_id=ADMIN_ID)
    manifest = service.load_manifest()
    binding = run["batch_plan"][0]
    assert binding["manifest_checksum_sha256"] == manifest["manifest_checksum_sha256"]
    assert len(binding["batch_ids"]) == len(manifest["batches"])


def test_execute_registered_batch_runs_the_real_manifest_command(settings: Settings) -> None:
    service = ProductionRegressionService(settings)
    run = service.create_manifest_run(admin_id=ADMIN_ID)
    result = service.execute_registered_batch(run["public_id"], "secret_scan_01", admin_id=ADMIN_ID)
    assert result["status"] == "passed"
    assert result["passed_count"] > 0
    assert result["batch_name"] == "secret_scan:secret_scan_01"


def test_execute_registered_batch_rejects_unregistered_batch_id(settings: Settings) -> None:
    service = ProductionRegressionService(settings)
    run = service.create_manifest_run(admin_id=ADMIN_ID)
    with pytest.raises(ValidationError, match="not part of this run's manifest"):
        service.execute_registered_batch(
            run["public_id"], "totally_made_up_batch", admin_id=ADMIN_ID
        )


def test_execute_registered_batch_rejects_when_manifest_changed_since_run_creation(
    settings: Settings, tmp_path: Path
) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, _tiny_valid_manifest())
    service = ProductionRegressionService(settings, manifest_path=manifest_path)
    run = service.create_manifest_run(admin_id=ADMIN_ID)

    changed = _tiny_valid_manifest()
    changed["name"] = "a different manifest"
    changed["manifest_checksum_sha256"] = compute_manifest_checksum(changed)
    _write_manifest(manifest_path, changed)

    with pytest.raises(ValidationError, match="manifest has changed"):
        service.execute_registered_batch(
            run["public_id"], f"{sorted(REQUIRED_MANIFEST_CATEGORIES)[0]}_01", admin_id=ADMIN_ID
        )


def test_execute_registered_batch_rejects_concurrent_execution_on_same_run(
    settings: Settings, tmp_path: Path
) -> None:
    manifest = _tiny_valid_manifest()
    # A slow batch so the second call reliably observes the lock held.
    for batch in manifest["batches"]:
        if batch["batch_id"] == "backend_services_01":
            batch["command"] = ["${PYTHON}", "-c", "import time; time.sleep(2)"]
            batch["timeout_seconds"] = 10
    manifest["manifest_checksum_sha256"] = compute_manifest_checksum(manifest)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, manifest)

    service = ProductionRegressionService(settings, manifest_path=manifest_path)
    run = service.create_manifest_run(admin_id=ADMIN_ID)

    def _run_slow_batch() -> None:
        service.execute_registered_batch(
            run["public_id"], "backend_services_01", admin_id=ADMIN_ID
        )

    thread = threading.Thread(target=_run_slow_batch)
    thread.start()
    try:
        import time

        time.sleep(0.3)
        with pytest.raises(ValidationError, match="only one batch may run at a time"):
            service.execute_registered_batch(
                run["public_id"], "database_integrity_01", admin_id=ADMIN_ID
            )
    finally:
        thread.join(timeout=10)


def test_finalize_manifest_run_blocked_when_required_batches_missing(settings: Settings) -> None:
    service = ProductionRegressionService(settings)
    run = service.create_manifest_run(admin_id=ADMIN_ID)
    service.execute_registered_batch(run["public_id"], "secret_scan_01", admin_id=ADMIN_ID)
    finalized = service.finalize_manifest_run(run["public_id"], admin_id=ADMIN_ID)
    assert finalized["fine_status"] == "blocked"
    assert "secret_scan_01" not in finalized["missing_required_batch_ids"]


def test_finalize_manifest_run_passed_when_all_required_batches_pass(
    settings: Settings, tmp_path: Path
) -> None:
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, _tiny_valid_manifest())
    service = ProductionRegressionService(settings, manifest_path=manifest_path)
    run = service.create_manifest_run(admin_id=ADMIN_ID)
    for category in sorted(REQUIRED_MANIFEST_CATEGORIES):
        service.execute_registered_batch(run["public_id"], f"{category}_01", admin_id=ADMIN_ID)
    finalized = service.finalize_manifest_run(run["public_id"], admin_id=ADMIN_ID)
    assert finalized["fine_status"] == "passed"
    assert finalized["status"] == "completed"


def test_finalize_manifest_run_failed_when_a_required_batch_fails(
    settings: Settings, tmp_path: Path
) -> None:
    manifest = _tiny_valid_manifest()
    for batch in manifest["batches"]:
        if batch["category"] == sorted(REQUIRED_MANIFEST_CATEGORIES)[0]:
            batch["command"] = ["${PYTHON}", "-c", "import sys; sys.exit(1)"]
    manifest["manifest_checksum_sha256"] = compute_manifest_checksum(manifest)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, manifest)

    service = ProductionRegressionService(settings, manifest_path=manifest_path)
    run = service.create_manifest_run(admin_id=ADMIN_ID)
    for category in sorted(REQUIRED_MANIFEST_CATEGORIES):
        service.execute_registered_batch(run["public_id"], f"{category}_01", admin_id=ADMIN_ID)
    finalized = service.finalize_manifest_run(run["public_id"], admin_id=ADMIN_ID)
    assert finalized["fine_status"] == "failed"
    assert finalized["status"] == "completed_with_failures"


def test_secret_patterns_are_redacted_from_raw_summary(settings: Settings, tmp_path: Path) -> None:
    manifest = _tiny_valid_manifest()
    category = sorted(REQUIRED_MANIFEST_CATEGORIES)[0]
    for batch in manifest["batches"]:
        if batch["category"] == category:
            batch["command"] = [
                "${PYTHON}", "-c",
                "print('token sk-abcdefghijklmnopqrstuvwxyz123456 leaked')",
            ]
    manifest["manifest_checksum_sha256"] = compute_manifest_checksum(manifest)
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, manifest)

    service = ProductionRegressionService(settings, manifest_path=manifest_path)
    run = service.create_manifest_run(admin_id=ADMIN_ID)
    result = service.execute_registered_batch(
        run["public_id"], f"{category}_01", admin_id=ADMIN_ID
    )
    assert "sk-abcdefghijklmnopqrstuvwxyz123456" not in result["raw_summary"]
    assert "[REDACTED]" in result["raw_summary"]
