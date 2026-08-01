from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.dataset_sample_deletion_service import (
    DatasetSampleDeletionError,
    ExternalDatasetSampleDeletionService,
)
from backend.services.dataset_sample_quarantine_service import ExternalDatasetQuarantineService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "deletion.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        quarantine_dir=tmp_path / "quarantine",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def sample_import(settings: Settings) -> dict:
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
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    return samples.create_sample_import(
        {
            "sample_import_code": "SI-1",
            "verification_case_public_id": case["public_id"],
            "candidate_public_id": candidate["public_id"],
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )


def test_request_deletion_requires_nonempty_reason(settings: Settings, sample_import: dict) -> None:
    service = ExternalDatasetSampleDeletionService(settings)
    with pytest.raises(DatasetSampleDeletionError):
        service.request_deletion(sample_import["public_id"], admin_id=ADMIN_ID, reason="  ")


def test_request_deletion_includes_lineage_impact_summary(
    settings: Settings, sample_import: dict
) -> None:
    service = ExternalDatasetSampleDeletionService(settings)
    request = service.request_deletion(
        sample_import["public_id"], admin_id=ADMIN_ID, reason="No longer needed"
    )
    assert request["status"] == "requested"
    assert "files" in request["lineage_impact_summary"]


def test_execute_deletion_requires_confirmation_first(
    settings: Settings, sample_import: dict
) -> None:
    service = ExternalDatasetSampleDeletionService(settings)
    request = service.request_deletion(
        sample_import["public_id"], admin_id=ADMIN_ID, reason="cleanup"
    )
    with pytest.raises(DatasetSampleDeletionError):
        service.execute_deletion(request["deletion_request_code"], admin_id=ADMIN_ID)


def test_full_deletion_lifecycle_removes_payload_but_keeps_manifest(
    settings: Settings, sample_import: dict
) -> None:
    quarantine = ExternalDatasetQuarantineService(settings)
    quarantine.ensure_layout(sample_import["public_id"])
    quarantine.original_file_path(sample_import["public_id"], "a.txt").write_bytes(b"payload")

    service = ExternalDatasetSampleDeletionService(settings)
    request = service.request_deletion(
        sample_import["public_id"], admin_id=ADMIN_ID, reason="cleanup"
    )
    service.confirm_deletion(request["deletion_request_code"], admin_id=REVIEWER_ID)
    executed = service.execute_deletion(request["deletion_request_code"], admin_id=REVIEWER_ID)
    assert executed["status"] == "executed"

    assert not quarantine.original_dir(sample_import["public_id"]).exists()
    assert quarantine.manifest_path(sample_import["public_id"]).exists()

    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    refreshed = samples.get_sample_import(sample_import["public_id"])
    assert refreshed["status"] == "deleted"
    assert refreshed["deleted_at"] is not None


def test_deletion_preserves_audit_history_and_reports(
    settings: Settings, sample_import: dict
) -> None:
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    samples.add_report(
        sample_import["public_id"],
        {
            "rag_sandbox_eligible": False,
            "training_assessment_status": "not_assessed",
            "report": {"summary": "test"},
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    service = ExternalDatasetSampleDeletionService(settings)
    request = service.request_deletion(
        sample_import["public_id"], admin_id=ADMIN_ID, reason="cleanup"
    )
    service.confirm_deletion(request["deletion_request_code"], admin_id=REVIEWER_ID)
    service.execute_deletion(request["deletion_request_code"], admin_id=REVIEWER_ID)

    reports = samples.list_reports(sample_import["public_id"])
    assert len(reports) == 1
    events = samples.list_events(sample_import["public_id"])
    assert any(event["event_type"] == "deletion_executed" for event in events)


def test_deletion_lifecycle_is_append_only_history(
    settings: Settings, sample_import: dict
) -> None:
    service = ExternalDatasetSampleDeletionService(settings)
    request = service.request_deletion(
        sample_import["public_id"], admin_id=ADMIN_ID, reason="cleanup"
    )
    service.confirm_deletion(request["deletion_request_code"], admin_id=REVIEWER_ID)
    service.execute_deletion(request["deletion_request_code"], admin_id=REVIEWER_ID)

    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    history = samples.list_deletion_requests(sample_import["public_id"])
    assert [row["status"] for row in history] == ["requested", "confirmed", "executed"]


def test_cancel_deletion_stops_before_execution(settings: Settings, sample_import: dict) -> None:
    service = ExternalDatasetSampleDeletionService(settings)
    request = service.request_deletion(
        sample_import["public_id"], admin_id=ADMIN_ID, reason="cleanup"
    )
    cancelled = service.cancel_deletion(request["deletion_request_code"], admin_id=ADMIN_ID)
    assert cancelled["status"] == "cancelled"
    with pytest.raises(DatasetSampleDeletionError):
        service.execute_deletion(request["deletion_request_code"], admin_id=ADMIN_ID)
