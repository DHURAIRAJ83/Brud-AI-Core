"""Phase 12 Step 37 security tests.

Complements the fine-grained checks already covered in each service's
own test file (SSRF/private-IP/redirect/byte-limit in
`test_dataset_sample_download_transport.py`, path-traversal/archive-
bomb/symlink/encrypted-entry in `test_dataset_sample_archive_safety_
service.py`, executable/MIME-mismatch/CSV-formula-injection/pickle in
`test_dataset_sample_security_scan_service.py`, stale-approval/expired-
verification/blocked-provider in `test_dataset_sample_eligibility_
service.py`, and public-file-URL/CSRF/auth in `test_dataset_sample_
import_api.py`) with the cross-cutting checks that need their own
file: a structural no-execution scan across every Phase 12 module
(mirrors Phase 11's own `test_dataset_verification_security.py`),
expired-approval enforcement, and PII/secret redaction in summaries
and audit metadata.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.core.json_utils import redact_secrets
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.dataset_sample_download_service import (
    DatasetSampleDownloadError,
    ExternalDatasetSampleDownloadService,
)
from backend.services.dataset_sample_download_transport import StreamResponse
from backend.services.dataset_sample_eligibility_service import (
    ExternalDatasetSampleApprovalService,
    ExternalDatasetSampleEligibilityService,
)
from backend.services.dataset_sample_pii_safety_service import ExternalDatasetPIIScanService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"

PHASE12_MODULES = (
    "backend/services/dataset_sample_archive_safety_service.py",
    "backend/services/dataset_sample_contamination_service.py",
    "backend/services/dataset_sample_deletion_service.py",
    "backend/services/dataset_sample_download_service.py",
    "backend/services/dataset_sample_download_transport.py",
    "backend/services/dataset_sample_duplicate_service.py",
    "backend/services/dataset_sample_eligibility_service.py",
    "backend/services/dataset_sample_file_validation_service.py",
    "backend/services/dataset_sample_language_service.py",
    "backend/services/dataset_sample_normalization_service.py",
    "backend/services/dataset_sample_parsing_service.py",
    "backend/services/dataset_sample_pii_safety_service.py",
    "backend/services/dataset_sample_pipeline_service.py",
    "backend/services/dataset_sample_poisoning_service.py",
    "backend/services/dataset_sample_quality_service.py",
    "backend/services/dataset_sample_quarantine_service.py",
    "backend/services/dataset_sample_report_service.py",
    "backend/services/dataset_sample_review_service.py",
    "backend/services/dataset_sample_security_scan_service.py",
    "backend/database/repositories/dataset_sample_import.py",
    "backend/api/routes/dataset_sample_import.py",
)

_FORBIDDEN_CALL_NAMES = frozenset({"eval", "exec", "compile", "__import__"})
_FORBIDDEN_MODULES = frozenset({"subprocess", "os.system", "pickle", "shutil.rmtree"})
_FORBIDDEN_TABLES = (
    "dataset_records", "manual_data_records", "semantic_chunks",
    "structured_record_candidates", "rag_", "training_", "evaluation_",
)


def _module_source(relative_path: str) -> str:
    return (Path(__file__).resolve().parents[2] / relative_path).read_text(encoding="utf-8")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "security.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        quarantine_dir=tmp_path / "quarantine",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _finalized_case(settings: Settings) -> dict:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "Corpus", "normalized_name": "corpus"}
    )
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    verification.update_case(case["public_id"], {"identity_status": "verified"})
    for permission_type in ("rag_use", "evaluation_use"):
        verification.assess_permission(
            case["public_id"], permission_type,
            {"candidate_public_id": candidate["public_id"], "status": "likely_allowed"},
        )
        verification.review_permission(
            case["public_id"], permission_type,
            status="approved", reviewed_by=ADMIN_ID, reason="ok",
        )
    return verification.lock_case(case["public_id"], {"summary": "done"})


# -- structural no-execution / no-full-dataset-write scan --------------------------------


@pytest.mark.parametrize("relative_path", PHASE12_MODULES)
def test_module_never_calls_eval_exec_or_a_shell(relative_path: str) -> None:
    source = _module_source(relative_path)
    tree = ast.parse(source, filename=relative_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in _FORBIDDEN_CALL_NAMES, (
                f"{relative_path} calls forbidden builtin {node.func.id}"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in ("subprocess",), f"{relative_path} imports subprocess"
    assert "subprocess" not in source, f"{relative_path} references subprocess"
    assert "os.system(" not in source, f"{relative_path} calls os.system"


@pytest.mark.parametrize("relative_path", PHASE12_MODULES)
def test_module_never_writes_to_a_full_dataset_or_rag_or_training_table(
    relative_path: str,
) -> None:
    source = _module_source(relative_path)
    lowered = source.lower()
    for forbidden in _FORBIDDEN_TABLES:
        assert f"insert into {forbidden}" not in lowered, (
            f"{relative_path} inserts into a forbidden table matching '{forbidden}'"
        )


@pytest.mark.parametrize("relative_path", PHASE12_MODULES)
def test_module_never_spells_training_approved(relative_path: str) -> None:
    source = _module_source(relative_path)
    assert "training_approved" not in source


def test_no_module_clones_a_repository() -> None:
    for relative_path in PHASE12_MODULES:
        source = _module_source(relative_path)
        assert "git clone" not in source.lower()
        assert "GitPython" not in source


# -- expired approval -----------------------------------------------------------------


def test_download_rejects_an_expired_approval(settings: Settings) -> None:
    case = _finalized_case(settings)
    eligibility = ExternalDatasetSampleEligibilityService(settings)
    sample_import = eligibility.create_sample_import(
        case["public_id"],
        {
            "purpose": "manual_review", "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    approvals = ExternalDatasetSampleApprovalService(settings)
    approval = approvals.request_approval(
        sample_import["public_id"],
        {"purpose": "manual_review", "requested_record_limit": 10, "requested_byte_limit": 100},
        admin_id=ADMIN_ID,
    )
    approvals.approve(
        approval["public_id"],
        admin_id=ADMIN_ID,
        approved_record_limit=10,
        approved_byte_limit=100,
        expires_at="2020-01-01T00:00:00",  # already in the past
    )

    def fake_transport(url: str, headers: dict, timeout_seconds: float) -> StreamResponse:
        return StreamResponse(status_code=200, headers={}, chunk_iterator=iter([b"data"]))

    service = ExternalDatasetSampleDownloadService(
        settings, transport=fake_transport, resolver=lambda host: ["93.184.216.34"]
    )
    with pytest.raises(DatasetSampleDownloadError, match="expired"):
        service.download_file(
            sample_import["public_id"],
            source_url="https://example.org/data.txt",
            allowed_domains={"example.org"},
            admin_id=ADMIN_ID,
        )


def test_download_succeeds_with_a_future_expiry(settings: Settings) -> None:
    case = _finalized_case(settings)
    eligibility = ExternalDatasetSampleEligibilityService(settings)
    sample_import = eligibility.create_sample_import(
        case["public_id"],
        {
            "purpose": "manual_review", "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    approvals = ExternalDatasetSampleApprovalService(settings)
    approval = approvals.request_approval(
        sample_import["public_id"],
        {"purpose": "manual_review", "requested_record_limit": 10, "requested_byte_limit": 100},
        admin_id=ADMIN_ID,
    )
    approvals.approve(
        approval["public_id"],
        admin_id=ADMIN_ID,
        approved_record_limit=10,
        approved_byte_limit=100,
        expires_at="2099-01-01T00:00:00",
    )

    def fake_transport(url: str, headers: dict, timeout_seconds: float) -> StreamResponse:
        return StreamResponse(status_code=200, headers={}, chunk_iterator=iter([b"data"]))

    service = ExternalDatasetSampleDownloadService(
        settings, transport=fake_transport, resolver=lambda host: ["93.184.216.34"]
    )
    result = service.download_file(
        sample_import["public_id"],
        source_url="https://example.org/data.txt",
        allowed_domains={"example.org"},
        admin_id=ADMIN_ID,
    )
    assert result["size_bytes"] == 4


# -- PII / secret redaction --------------------------------------------------------------


def test_pii_scan_result_never_embeds_the_raw_matched_value() -> None:
    result = ExternalDatasetPIIScanService().scan("Contact admin@example.com or call 9876543210")
    serialized = str(result["findings"])
    assert "admin@example.com" not in serialized
    assert "9876543210" not in serialized


def test_redact_secrets_scrubs_secret_shaped_audit_metadata() -> None:
    metadata = {"api_key": "sk-live-abcdef", "password": "hunter2", "note": "fine"}
    redacted = redact_secrets(metadata)
    assert redacted["api_key"] != "sk-live-abcdef"
    assert redacted["password"] != "hunter2"
    assert redacted["note"] == "fine"


# -- audit completeness -------------------------------------------------------------------


@pytest.mark.parametrize(
    "relative_path,expected_actions",
    [
        (
            "backend/services/dataset_sample_eligibility_service.py",
            ("create_sample_import", "request_sample_import_approval", "approve_sample_import",
             "reject_sample_import_approval"),
        ),
        ("backend/services/dataset_sample_download_service.py", ("download_approved_sample",)),
        (
            "backend/services/dataset_sample_review_service.py",
            ("review_sample_issue",),
        ),
        (
            "backend/services/dataset_sample_report_service.py",
            ("finalize_sample_validation_report",),
        ),
        (
            "backend/services/dataset_sample_deletion_service.py",
            ("request_sample_deletion", "confirm_sample_deletion", "execute_sample_deletion",
             "cancel_sample_deletion"),
        ),
    ],
)
def test_every_mutating_service_audits_its_real_action_strings(
    relative_path: str, expected_actions: tuple[str, ...]
) -> None:
    source = _module_source(relative_path)
    for action in expected_actions:
        assert f'action="{action}"' in source, f"{relative_path} never audits action={action!r}"
