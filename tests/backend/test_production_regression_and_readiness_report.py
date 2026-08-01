import base64
import os
import shutil
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.services.production_api_abuse_readiness_service import (
    ProductionApiAbuseReadinessService,
)
from backend.services.production_artifact_security_service import ProductionArtifactSecurityService
from backend.services.production_backup_restore_readiness_service import (
    ProductionBackupEncryptionAssessmentService,
    ProductionBackupEncryptionService,
    ProductionBackupReadinessService,
    ProductionRestoreReadinessService,
)
from backend.services.production_readiness_report_service import (
    ProductionAcceptanceReviewService,
    ProductionReadinessReportService,
)
from backend.services.production_regression_service import ProductionRegressionService
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


def _passing_test_file(tmp_path: Path) -> Path:
    path = tmp_path / "test_trivial_passing.py"
    path.write_text("def test_trivial_ok():\n    assert True\n", encoding="utf-8")
    return path


def _failing_test_file(tmp_path: Path) -> Path:
    path = tmp_path / "test_trivial_failing.py"
    path.write_text("def test_trivial_fails():\n    assert False\n", encoding="utf-8")
    return path


def _slow_test_file(tmp_path: Path) -> Path:
    path = tmp_path / "test_trivial_slow.py"
    path.write_text(
        "import time\n\ndef test_trivial_slow():\n    time.sleep(5)\n    assert True\n",
        encoding="utf-8",
    )
    return path


def _all_readiness_checks_pass(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.resolved_backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        settings.resolved_database_path,
        settings.resolved_backup_dir / "brud_ai_before_v37_20260101000000.db",
    )
    ProductionBackupReadinessService(settings).check_backup_readiness(admin_id=ADMIN_ID)
    ProductionRestoreReadinessService(settings).check_restore_readiness(admin_id=ADMIN_ID)
    ProductionApiAbuseReadinessService(settings).assess(admin_id=ADMIN_ID)
    ProductionSecretScanService(settings).verify_redaction_mechanism(admin_id=ADMIN_ID)
    ProductionArtifactSecurityService(settings).check_backup_artifact(admin_id=ADMIN_ID)

    # Phase 15A Step 22 evidence: canonical regression, browser
    # verification, and backup encryption. The browser-e2e/canonical-
    # regression evidence is recorded at the repository layer directly
    # (as a completed real run would have left it) rather than running a
    # real Playwright suite inside this unit test.
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
    monkeypatch.setenv(
        settings.backup_encryption_key_env_var,
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
    )
    ProductionBackupEncryptionService(settings).encrypt_latest_backup(admin_id=ADMIN_ID)
    ProductionBackupEncryptionAssessmentService(settings).assess(admin_id=ADMIN_ID)


# -- regression --------------------------------------------------------------------------------


def test_create_run_requires_batch_plan(settings: Settings) -> None:
    service = ProductionRegressionService(settings)
    with pytest.raises(ValidationError):
        service.create_run([], admin_id=ADMIN_ID)


def test_execute_batch_records_real_pytest_pass(settings: Settings, tmp_path: Path) -> None:
    test_file = _passing_test_file(tmp_path)
    service = ProductionRegressionService(settings)
    run = service.create_run(
        [{"batch_name": "trivial", "command": [str(test_file)]}], admin_id=ADMIN_ID,
    )
    result = service.execute_batch(
        run["public_id"], "trivial", [str(test_file)], admin_id=ADMIN_ID,
    )
    assert result["status"] == "passed"
    assert result["passed_count"] == 1
    assert result["failed_count"] == 0


def test_execute_batch_records_real_pytest_failure(settings: Settings, tmp_path: Path) -> None:
    test_file = _failing_test_file(tmp_path)
    service = ProductionRegressionService(settings)
    run = service.create_run(
        [{"batch_name": "trivial", "command": [str(test_file)]}], admin_id=ADMIN_ID,
    )
    result = service.execute_batch(
        run["public_id"], "trivial", [str(test_file)], admin_id=ADMIN_ID,
    )
    assert result["status"] == "failed"
    assert result["failed_count"] == 1


def test_execute_batch_records_environment_incomplete_on_timeout(
    settings: Settings, tmp_path: Path
) -> None:
    test_file = _slow_test_file(tmp_path)
    service = ProductionRegressionService(settings)
    run = service.create_run(
        [{"batch_name": "slow", "command": [str(test_file)]}], admin_id=ADMIN_ID,
    )
    result = service.execute_batch(
        run["public_id"], "slow", [str(test_file)], admin_id=ADMIN_ID, timeout_seconds=1,
    )
    assert result["status"] == "environment_incomplete"


def test_finalize_run_requires_results(settings: Settings) -> None:
    service = ProductionRegressionService(settings)
    run = service.create_run(
        [{"batch_name": "trivial", "command": []}], admin_id=ADMIN_ID,
    )
    with pytest.raises(ValidationError):
        service.finalize_run(run["public_id"], admin_id=ADMIN_ID)


def test_finalize_run_status_derivation(settings: Settings, tmp_path: Path) -> None:
    passing = _passing_test_file(tmp_path)
    failing = _failing_test_file(tmp_path)
    service = ProductionRegressionService(settings)

    run = service.create_run(
        [{"batch_name": "a", "command": [str(passing)]}], admin_id=ADMIN_ID,
    )
    service.execute_batch(run["public_id"], "a", [str(passing)], admin_id=ADMIN_ID)
    finalized = service.finalize_run(run["public_id"], admin_id=ADMIN_ID)
    assert finalized["status"] == "completed"

    run_2 = service.create_run(
        [{"batch_name": "b", "command": [str(failing)]}], admin_id=ADMIN_ID,
    )
    service.execute_batch(run_2["public_id"], "b", [str(failing)], admin_id=ADMIN_ID)
    finalized_2 = service.finalize_run(run_2["public_id"], admin_id=ADMIN_ID)
    assert finalized_2["status"] == "completed_with_failures"


# -- readiness report --------------------------------------------------------------------------


def test_compile_report_not_ready_when_nothing_assessed(settings: Settings) -> None:
    service = ProductionReadinessReportService(settings)
    report = service.compile_report(admin_id=ADMIN_ID)
    assert report["recommendation"] == "not_ready"
    assert report["report_version"] == 1


def test_compile_report_ready_for_production_when_everything_passes(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _all_readiness_checks_pass(settings, monkeypatch)
    passing = _passing_test_file(tmp_path)
    regression_service = ProductionRegressionService(settings)
    run = regression_service.create_run(
        [{"batch_name": "a", "command": [str(passing)]}], admin_id=ADMIN_ID,
    )
    regression_service.execute_batch(run["public_id"], "a", [str(passing)], admin_id=ADMIN_ID)
    regression_service.finalize_run(run["public_id"], admin_id=ADMIN_ID)

    report_service = ProductionReadinessReportService(settings)
    report = report_service.compile_report(admin_id=ADMIN_ID)
    assert report["recommendation"] == "ready_for_text_nlp_production", report["report"]


def test_compile_report_ready_with_conditions_when_regression_has_environment_limitations(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Everything else genuinely passes, but the canonical regression run's
    # own finalize step classified it as environment-limited (not a
    # product failure) -- the recommendation must reflect that honestly
    # as conditional, never silently upgrade it to the unconditional
    # "ready_for_text_nlp_production".
    _all_readiness_checks_pass(settings, monkeypatch)
    repository = ProductionReadinessRepository(settings.resolved_database_path)
    repository.record_readiness_event(
        {
            "event_type": "canonical_regression_finalized",
            "resource_type": "production_regression_run",
            "resource_public_id": "REG-test0000000000000001",
            "summary": "result_status=passed_with_environment_limitations",
            "metadata": {},
            "performed_by_admin_public_id": ADMIN_ID,
        }
    )

    report = ProductionReadinessReportService(settings).compile_report(admin_id=ADMIN_ID)
    assert report["recommendation"] == "ready_with_conditions", report["report"]


def test_compile_report_versions_increment_and_are_immutable(settings: Settings) -> None:
    service = ProductionReadinessReportService(settings)
    report_1 = service.compile_report(admin_id=ADMIN_ID)
    report_2 = service.compile_report(admin_id=ADMIN_ID)
    assert report_2["report_version"] == report_1["report_version"] + 1
    assert report_1["public_id"] != report_2["public_id"]


# -- acceptance review -------------------------------------------------------------------------


def test_submit_review_rejects_stale_report(settings: Settings) -> None:
    report_service = ProductionReadinessReportService(settings)
    report_1 = report_service.compile_report(admin_id=ADMIN_ID)
    report_service.compile_report(admin_id=ADMIN_ID)

    review_service = ProductionAcceptanceReviewService(settings)
    with pytest.raises(ValidationError):
        review_service.submit_review(
            report_1["public_id"], "accepted", "looks fine", admin_id=ADMIN_ID,
        )


def test_submit_review_rejects_unknown_decision(settings: Settings) -> None:
    report_service = ProductionReadinessReportService(settings)
    report = report_service.compile_report(admin_id=ADMIN_ID)
    review_service = ProductionAcceptanceReviewService(settings)
    with pytest.raises(ValidationError):
        review_service.submit_review(
            report["public_id"], "sure_why_not", "reason", admin_id=ADMIN_ID,
        )


def test_submit_review_rejects_empty_reason(settings: Settings) -> None:
    report_service = ProductionReadinessReportService(settings)
    report = report_service.compile_report(admin_id=ADMIN_ID)
    review_service = ProductionAcceptanceReviewService(settings)
    with pytest.raises(ValidationError):
        review_service.submit_review(
            report["public_id"], "accepted", "   ", admin_id=ADMIN_ID,
        )


def test_submit_review_binds_report_checksum_and_fingerprint(settings: Settings) -> None:
    report_service = ProductionReadinessReportService(settings)
    report = report_service.compile_report(admin_id=ADMIN_ID)
    review_service = ProductionAcceptanceReviewService(settings)
    review = review_service.submit_review(
        report["public_id"], "needs_remediation", "backup readiness never assessed",
        admin_id=ADMIN_ID,
    )
    assert review["report_checksum"] == report["report_checksum_sha256"]
    assert review["target_fingerprint"]
    assert review["decision"] == "needs_remediation"
