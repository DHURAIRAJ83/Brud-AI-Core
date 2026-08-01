from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.dataset_sample_report_service import (
    DatasetSampleReportError,
    ExternalDatasetSampleReportService,
)
from backend.services.dataset_sample_review_service import ExternalDatasetSampleReviewService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "report.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
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


def _sample_import_with_accepted_record(settings: Settings) -> dict:
    case = _finalized_case(settings)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": "SI-1",
            "verification_case_public_id": case["public_id"],
            "candidate_public_id": case["candidate_public_id"],
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    file = samples.add_file(
        sample_import["public_id"],
        {"original_filename": "a.txt", "safe_filename": "a.txt", "relative_path": "a.txt"},
    )
    record = samples.add_record(
        sample_import["public_id"],
        {
            "source_file_public_id": file["public_id"],
            "raw_content": "hello",
            "normalized_content": "hello",
            "source_checksum": "a" * 64,
            "record_checksum": "b" * 64,
        },
    )
    samples.update_record_status(record["public_id"], "accepted")
    return sample_import


def test_finalize_succeeds_and_produces_rag_sandbox_eligible_report(settings: Settings) -> None:
    sample_import = _sample_import_with_accepted_record(settings)
    service = ExternalDatasetSampleReportService(settings)
    finalized = service.finalize(sample_import["public_id"], admin_id=ADMIN_ID)
    assert finalized["locked_at"] is not None
    assert finalized["rag_sandbox_eligible"] is True
    assert finalized["training_assessment_status"] == "potentially_suitable"
    assert finalized["status"] == "validated"

    report = service.get_latest_report(sample_import["public_id"])
    assert report["rag_sandbox_eligible"] is True
    assert "recommended_next_step" in report["report"]


def test_finalize_refuses_when_already_finalized(settings: Settings) -> None:
    sample_import = _sample_import_with_accepted_record(settings)
    service = ExternalDatasetSampleReportService(settings)
    service.finalize(sample_import["public_id"], admin_id=ADMIN_ID)
    with pytest.raises(DatasetSampleReportError):
        service.finalize(sample_import["public_id"], admin_id=ADMIN_ID)


def test_finalize_blocked_by_unresolved_blocked_scan_result(settings: Settings) -> None:
    sample_import = _sample_import_with_accepted_record(settings)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    file = samples.add_file(
        sample_import["public_id"],
        {"original_filename": "b.exe", "safe_filename": "b.exe", "relative_path": "b.exe"},
    )
    samples.record_scan_result(
        sample_import["public_id"], {"file_public_id": file["public_id"], "verdict": "blocked"}
    )
    service = ExternalDatasetSampleReportService(settings)
    with pytest.raises(DatasetSampleReportError):
        service.finalize(sample_import["public_id"], admin_id=ADMIN_ID)


def test_finalize_succeeds_after_blocked_scan_result_is_reviewed(settings: Settings) -> None:
    sample_import = _sample_import_with_accepted_record(settings)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    file = samples.add_file(
        sample_import["public_id"],
        {"original_filename": "b.exe", "safe_filename": "b.exe", "relative_path": "b.exe"},
    )
    samples.record_scan_result(
        sample_import["public_id"], {"file_public_id": file["public_id"], "verdict": "blocked"}
    )
    review_service = ExternalDatasetSampleReviewService(settings)
    review_service.review_target(
        sample_import["public_id"],
        target_type="file",
        target_id=file["public_id"],
        decision="accept",
        reason="Manually verified safe despite the scan flag",
        reviewer_admin_public_id=REVIEWER_ID,
    )
    service = ExternalDatasetSampleReportService(settings)
    finalized = service.finalize(sample_import["public_id"], admin_id=ADMIN_ID)
    assert finalized["locked_at"] is not None


def test_finalize_blocked_by_unresolved_blocked_pii_issue(settings: Settings) -> None:
    sample_import = _sample_import_with_accepted_record(settings)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    samples.add_record_issue(
        sample_import["public_id"],
        {"issue_category": "pii", "issue_type": "api_key", "status": "blocked"},
    )
    service = ExternalDatasetSampleReportService(settings)
    with pytest.raises(DatasetSampleReportError):
        service.finalize(sample_import["public_id"], admin_id=ADMIN_ID)


def test_finalize_not_rag_eligible_when_pii_issue_unresolved_but_not_blocked(
    settings: Settings,
) -> None:
    sample_import = _sample_import_with_accepted_record(settings)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    samples.add_record_issue(
        sample_import["public_id"],
        {"issue_category": "pii", "issue_type": "email_address", "status": "possible"},
    )
    service = ExternalDatasetSampleReportService(settings)
    finalized = service.finalize(sample_import["public_id"], admin_id=ADMIN_ID)
    assert finalized["rag_sandbox_eligible"] is False
    assert finalized["status"] == "validated_with_conditions"


def test_finalize_training_assessment_blocked_on_confirmed_contamination(
    settings: Settings,
) -> None:
    sample_import = _sample_import_with_accepted_record(settings)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    samples.add_record_issue(
        sample_import["public_id"],
        {
            "issue_category": "contamination", "issue_type": "test_leakage",
            "status": "confirmed_overlap",
        },
    )
    service = ExternalDatasetSampleReportService(settings)
    finalized = service.finalize(sample_import["public_id"], admin_id=ADMIN_ID)
    assert finalized["training_assessment_status"] == "blocked"
    # Contamination against training/eval sets never automatically
    # disqualifies RAG-sandbox use on its own.
    assert finalized["rag_sandbox_eligible"] is True


def test_finalize_not_eligible_without_any_accepted_records(settings: Settings) -> None:
    case = _finalized_case(settings)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": "SI-empty",
            "verification_case_public_id": case["public_id"],
            "candidate_public_id": case["candidate_public_id"],
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    service = ExternalDatasetSampleReportService(settings)
    finalized = service.finalize(sample_import["public_id"], admin_id=ADMIN_ID)
    assert finalized["rag_sandbox_eligible"] is False
    assert finalized["training_assessment_status"] == "not_suitable"


def test_finalize_never_writes_a_training_approved_value(settings: Settings) -> None:
    sample_import = _sample_import_with_accepted_record(settings)
    service = ExternalDatasetSampleReportService(settings)
    finalized = service.finalize(sample_import["public_id"], admin_id=ADMIN_ID)
    assert finalized["training_assessment_status"] != "training_approved"
    assert "approved" not in finalized["training_assessment_status"]
