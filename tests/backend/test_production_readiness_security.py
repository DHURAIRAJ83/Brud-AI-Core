import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.services.production_backup_restore_readiness_service import (
    ProductionBackupReadinessService,
)
from backend.services.production_model_activation_service import ProductionModelActivationService
from backend.services.production_model_release_approval_service import (
    ProductionModelReleaseApprovalService,
)
from backend.services.production_rag_activation_service import ProductionRagActivationService
from backend.services.production_readiness_report_service import (
    ProductionAcceptanceReviewService,
    ProductionReadinessReportService,
)
from backend.services.production_regression_service import ProductionRegressionService
from backend.services.production_rollback_service import ProductionRollbackPlanService
from tests.backend.test_production_model_release_validation_activation import (
    _approved_admin_diagnostic_assignment,
    _approved_release_request,
    _assignment_service,
    _create_release,
    _profile,
)
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SERVICE_DIR = _REPO_ROOT / "backend" / "services"
_ROUTE_FILE = _REPO_ROOT / "backend" / "api" / "routes" / "production_readiness.py"
_PRODUCTION_SERVICE_FILES = sorted(_SERVICE_DIR.glob("production_*.py"))

_FORBIDDEN_RAW_MUTATION_PATTERNS = (
    "UPDATE inference_model_assignments",
    "lifecycle_status='active'",
    'lifecycle_status="active"',
)
# Deliberately excludes `rag_retrieval_profiles SET status='active'`:
# `RagRetrievalService.activate_profile()` only transitions draft/validated ->
# active, it cannot reactivate an already-archived profile, so
# `ProductionRagActivationService.rollback()` must set that column directly
# to restore the previously-active profile. This is a scoped, reasoned
# exception, not a bypass of governance -- it is still gated by this
# service's own approval/expiry/fingerprint checks before it runs.
_FORBIDDEN_NETWORK_IMPORTS = ("import requests", "import urllib.request", "import httpx")

# Phase 15A Step 32-33: defense in depth -- the backup-encryption key must
# only ever be read from the environment inside `_load_encryption_key()`,
# never anywhere else in this file (which would bypass its fail-closed
# validation, e.g. missing/malformed-key handling).
_BACKUP_ENCRYPTION_SERVICE_FILE = _SERVICE_DIR / "production_backup_restore_readiness_service.py"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "production_readiness_security.db",
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


# -- static analysis guards --------------------------------------------------------------------


def test_no_production_service_directly_mutates_activation_state() -> None:
    for path in _PRODUCTION_SERVICE_FILES:
        text = path.read_text(encoding="utf-8")
        for pattern in _FORBIDDEN_RAW_MUTATION_PATTERNS:
            assert pattern not in text, f"{path.name} contains forbidden pattern {pattern!r}"


def test_no_production_service_imports_a_new_network_library() -> None:
    for path in _PRODUCTION_SERVICE_FILES:
        text = path.read_text(encoding="utf-8")
        for marker in _FORBIDDEN_NETWORK_IMPORTS:
            assert marker not in text, f"{path.name} imports {marker!r}"


def test_production_readiness_routes_expose_no_download_endpoint() -> None:
    text = _ROUTE_FILE.read_text(encoding="utf-8")
    assert "download" not in text.lower()
    assert "FileResponse" not in text
    assert "StreamingResponse" not in text


def test_backup_encryption_key_value_is_only_read_by_one_function() -> None:
    # `_load_encryption_key()` is the only function allowed to read the
    # *value* of the key-reference env var (it fully validates and
    # returns key bytes for actual encrypt/decrypt use).
    # `ProductionBackupEncryptionAssessmentService.assess()` also reads
    # `os.environ` -- but only to compute a `bool` presence flag for the
    # honest Step 14 assessment, never the value itself. No other
    # function may reference `os.environ` at all.
    import ast

    text = _BACKUP_ENCRYPTION_SERVICE_FILE.read_text(encoding="utf-8")
    lines = text.split("\n")
    tree = ast.parse(text)
    allowed = {"_load_encryption_key", "assess"}
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        body_lines = lines[node.body[0].lineno - 1 : node.end_lineno]
        if "os.environ" in "\n".join(body_lines) and node.name not in allowed:
            offenders.append(node.name)
    assert offenders == [], f"os.environ referenced outside allowed functions: {offenders}"


def test_new_backup_encryption_mutating_routes_require_csrf() -> None:
    text = _ROUTE_FILE.read_text(encoding="utf-8")
    for route_path, function_name in (
        ("/secret-scan/backup-sidecar-files", "scan_backup_sidecar_files"),
        ("/backup-readiness/assess-encryption", "assess_backup_encryption"),
        ("/backup-readiness/encrypt", "encrypt_latest_backup"),
        ("/backup-readiness/verify-encrypted-restore", "verify_encrypted_restore"),
    ):
        assert f'@router.post("{route_path}")' in text, f"{route_path} is not a POST route"
        function_start = text.index(f"async def {function_name}(")
        function_signature = text[function_start:text.index(")", function_start)]
        assert "CsrfDependency" in function_signature, (
            f"{function_name} does not require CsrfDependency"
        )


# -- append-only triggers not already covered by the repository test suite ----------------------


def test_remaining_append_only_tables_reject_update_and_delete(settings: Settings) -> None:
    repository = ProductionReadinessRepository(settings.resolved_database_path)

    plan = ProductionRollbackPlanService(settings).create_plan(
        {"target_type": "model", "rollback_steps": ["x"]}, admin_id=ADMIN_ID,
    )
    repository.record_rollback_event(
        plan["public_id"], {"event_type": "validated", "performed_by_admin_public_id": ADMIN_ID},
    )
    backup_check = ProductionBackupReadinessService(settings).check_backup_readiness(
        admin_id=ADMIN_ID
    )
    deployment_check = repository.add_deployment_readiness_check(
        {"result_status": "not_ready", "created_by_admin_public_id": ADMIN_ID}
    )
    regression_run = ProductionRegressionService(settings).create_run(
        [{"batch_name": "x", "command": []}], admin_id=ADMIN_ID,
    )
    regression_result = repository.add_regression_result(
        regression_run["public_id"], {"batch_name": "x", "command": "x", "status": "passed"},
    )
    report = ProductionReadinessReportService(settings).compile_report(admin_id=ADMIN_ID)
    review = ProductionAcceptanceReviewService(settings).submit_review(
        report["public_id"], "needs_remediation", "nothing assessed", admin_id=ADMIN_ID,
    )

    checks = (
        ("production_rollback_events", "status", "used"),
        ("production_backup_readiness_checks", "result_status", "failed"),
        ("production_deployment_readiness_checks", "result_status", "ready"),
        ("production_regression_results", "status", "failed"),
        ("production_readiness_reports", "recommendation", "blocked"),
        ("production_acceptance_reviews", "decision", "accepted"),
    )
    public_ids = (
        None, backup_check["public_id"], deployment_check["public_id"],
        regression_result["public_id"], report["public_id"], review["public_id"],
    )

    with sqlite3.connect(settings.resolved_database_path) as connection:
        for (table, column, new_value), public_id in zip(checks, public_ids, strict=True):
            if public_id is None:
                continue
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    f"UPDATE {table} SET {column}=? WHERE public_id=?",  # noqa: S608
                    (new_value, public_id),
                )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(f"DELETE FROM {table} WHERE public_id=?", (public_id,))  # noqa: S608


# -- boundary / negative activation checks ------------------------------------------------------


def test_rag_activation_rejects_a_not_yet_validated_candidate(settings: Settings) -> None:
    from backend.services.production_rag_candidate_service import ProductionRagCandidateService
    from tests.backend.test_production_rag_validation_activation_rollback import (
        _approved_promotion_request,
    )

    request, _records = _approved_promotion_request(settings)
    candidate = ProductionRagCandidateService(settings).build_candidate(
        request["public_id"], admin_id=ADMIN_ID
    )
    assert candidate["status"] == "built"

    activation_service = ProductionRagActivationService(settings)
    with pytest.raises(ValidationError):
        activation_service.activate(candidate["public_id"], admin_id=ADMIN_ID)


def test_model_activation_rejects_a_stale_approval_fingerprint(settings: Settings) -> None:
    approved = _approved_release_request(settings)
    created_release = _create_release(
        settings, approved["model_release_candidate_public_id"], "0.1.0-stale",
    )
    assignment_service = _assignment_service(settings)
    profile_public_id = _profile(settings)
    assignment_public_id = _approved_admin_diagnostic_assignment(
        settings, assignment_service, created_release["public_id"], profile_public_id,
    )
    plan = ProductionRollbackPlanService(settings).create_plan(
        {"target_type": "model", "rollback_steps": ["x"]}, admin_id=ADMIN_ID,
    )
    ProductionRollbackPlanService(settings).validate_plan(plan["public_id"], admin_id=ADMIN_ID)

    # The request's evidence changes after approval was granted -- the
    # recomputed fingerprint at activation time must no longer match.
    with sqlite3.connect(settings.resolved_database_path) as connection:
        connection.execute(
            "UPDATE production_model_release_requests SET target_assignment_keys_json=? "
            "WHERE public_id=?",
            ('["a_new_target"]', approved["public_id"]),
        )

    activation_service = ProductionModelActivationService(settings)
    with pytest.raises(ValidationError, match="stale approval"):
        activation_service.activate(
            approved["public_id"], assignment_public_id, plan["public_id"], admin_id=ADMIN_ID,
        )


def test_model_activation_rejects_an_expired_approval(settings: Settings) -> None:
    from tests.backend.test_production_model_release_validation_activation import (
        _validated_release_request,
    )

    validated = _validated_release_request(settings)
    approval_service = ProductionModelReleaseApprovalService(settings)
    approval = approval_service.request_approval(validated["public_id"], admin_id=ADMIN_ID)
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    approval_service.approve(approval["public_id"], admin_id=ADMIN_ID, expires_at=past)

    created_release = _create_release(
        settings, validated["model_release_candidate_public_id"], "0.1.0-expired",
    )
    assignment_service = _assignment_service(settings)
    profile_public_id = _profile(settings)
    assignment_public_id = _approved_admin_diagnostic_assignment(
        settings, assignment_service, created_release["public_id"], profile_public_id,
    )
    plan = ProductionRollbackPlanService(settings).create_plan(
        {"target_type": "model", "rollback_steps": ["x"]}, admin_id=ADMIN_ID,
    )
    ProductionRollbackPlanService(settings).validate_plan(plan["public_id"], admin_id=ADMIN_ID)

    activation_service = ProductionModelActivationService(settings)
    with pytest.raises(ValidationError, match="expired"):
        activation_service.activate(
            validated["public_id"], assignment_public_id, plan["public_id"], admin_id=ADMIN_ID,
        )
