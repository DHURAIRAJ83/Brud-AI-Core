from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
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

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "download.db",
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
        session["public_id"],
        {"canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus"},
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


def _approved_sample_import(settings: Settings, *, approved_byte_limit: int = 1_000_000) -> dict:
    case = _finalized_case(settings)
    eligibility = ExternalDatasetSampleEligibilityService(settings)
    sample_import = eligibility.create_sample_import(
        case["public_id"],
        {
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    approvals = ExternalDatasetSampleApprovalService(settings)
    approval = approvals.request_approval(
        sample_import["public_id"],
        {
            "purpose": "manual_review",
            "requested_record_limit": 500,
            "requested_byte_limit": 1_000_000,
        },
        admin_id=ADMIN_ID,
    )
    approvals.approve(
        approval["public_id"],
        admin_id=ADMIN_ID,
        approved_record_limit=500,
        approved_byte_limit=approved_byte_limit,
        expires_at="2026-12-31T00:00:00",
    )
    return DatasetSampleImportRepository(settings.resolved_database_path).get_sample_import(
        sample_import["public_id"]
    )


def _fake_transport(chunks: list[bytes]):
    def transport(url: str, headers: dict, timeout_seconds: float) -> StreamResponse:
        return StreamResponse(status_code=200, headers={}, chunk_iterator=iter(chunks))

    return transport


def _resolver_public(_hostname: str) -> list[str]:
    return ["93.184.216.34"]


def test_download_file_succeeds_and_updates_file_and_quarantine_bytes(settings: Settings) -> None:
    sample_import = _approved_sample_import(settings)
    service = ExternalDatasetSampleDownloadService(
        settings, transport=_fake_transport([b"hello "]), resolver=_resolver_public
    )
    file_record = service.download_file(
        sample_import["public_id"],
        source_url="https://example.org/sample.txt",
        allowed_domains={"example.org"},
        admin_id=ADMIN_ID,
    )
    assert file_record["size_bytes"] == 6
    assert file_record["checksum"]

    refreshed = DatasetSampleImportRepository(settings.resolved_database_path).get_sample_import(
        sample_import["public_id"]
    )
    assert refreshed["status"] == "downloading"
    assert refreshed["quarantine_bytes_used"] >= 6


def test_download_file_requires_approved_approval(settings: Settings) -> None:
    case = _finalized_case(settings)
    eligibility = ExternalDatasetSampleEligibilityService(settings)
    sample_import = eligibility.create_sample_import(
        case["public_id"],
        {
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    service = ExternalDatasetSampleDownloadService(
        settings, transport=_fake_transport([b"data"]), resolver=_resolver_public
    )
    with pytest.raises(DatasetSampleDownloadError):
        service.download_file(
            sample_import["public_id"],
            source_url="https://example.org/sample.txt",
            allowed_domains={"example.org"},
            admin_id=ADMIN_ID,
        )


def test_download_file_rejects_when_approval_stale(settings: Settings) -> None:
    sample_import = _approved_sample_import(settings)
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    verification.update_case_reverification_fields(
        sample_import["verification_case_public_id"],
        {"verification_expiry_status": "source_changed"},
    )
    service = ExternalDatasetSampleDownloadService(
        settings, transport=_fake_transport([b"data"]), resolver=_resolver_public
    )
    with pytest.raises(DatasetSampleDownloadError):
        service.download_file(
            sample_import["public_id"],
            source_url="https://example.org/sample.txt",
            allowed_domains={"example.org"},
            admin_id=ADMIN_ID,
        )


def test_download_file_records_failure_event_when_byte_limit_exceeded_mid_stream(
    settings: Settings,
) -> None:
    small_import = _approved_sample_import(settings, approved_byte_limit=5)
    service = ExternalDatasetSampleDownloadService(
        settings, transport=_fake_transport([b"x" * 10]), resolver=_resolver_public
    )
    with pytest.raises(DatasetSampleDownloadError):
        service.download_file(
            small_import["public_id"],
            source_url="https://example.org/sample.txt",
            allowed_domains={"example.org"},
            admin_id=ADMIN_ID,
        )
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    events = samples.list_download_events(small_import["public_id"])
    assert any(event["event_type"] == "failed" for event in events)


def test_download_file_rejects_when_byte_quota_already_reached(settings: Settings) -> None:
    sample_import = _approved_sample_import(settings, approved_byte_limit=10)
    service = ExternalDatasetSampleDownloadService(
        settings, transport=_fake_transport([b"x" * 10]), resolver=_resolver_public
    )
    service.download_file(
        sample_import["public_id"],
        source_url="https://example.org/first.txt",
        allowed_domains={"example.org"},
        admin_id=ADMIN_ID,
    )
    with pytest.raises(DatasetSampleDownloadError):
        service.download_file(
            sample_import["public_id"],
            source_url="https://example.org/second.txt",
            allowed_domains={"example.org"},
            admin_id=ADMIN_ID,
        )


def test_mark_downloaded_transitions_status_to_quarantined(settings: Settings) -> None:
    sample_import = _approved_sample_import(settings)
    service = ExternalDatasetSampleDownloadService(
        settings, transport=_fake_transport([b"x"]), resolver=_resolver_public
    )
    service.download_file(
        sample_import["public_id"],
        source_url="https://example.org/sample.txt",
        allowed_domains={"example.org"},
        admin_id=ADMIN_ID,
    )
    updated = service.mark_downloaded(sample_import["public_id"], admin_id=ADMIN_ID)
    assert updated["status"] == "quarantined"
