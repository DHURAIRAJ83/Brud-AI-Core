from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.dataset_sample_review_service import (
    DatasetSampleReviewError,
    ExternalDatasetSampleReviewService,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "review.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
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


def test_review_target_creates_append_only_row(settings: Settings, sample_import: dict) -> None:
    service = ExternalDatasetSampleReviewService(settings)
    review = service.review_target(
        sample_import["public_id"],
        target_type="file",
        target_id="file-1",
        decision="accept",
        reason="Looks safe on manual inspection",
        reviewer_admin_public_id=REVIEWER_ID,
    )
    assert review["decision"] == "accept"
    reviews = service.list_reviews(sample_import["public_id"])
    assert len(reviews) == 1


def test_review_target_rejects_unknown_decision(settings: Settings, sample_import: dict) -> None:
    service = ExternalDatasetSampleReviewService(settings)
    with pytest.raises(DatasetSampleReviewError):
        service.review_target(
            sample_import["public_id"],
            target_type="file",
            target_id="file-1",
            decision="not_a_real_decision",
            reason="reason",
            reviewer_admin_public_id=REVIEWER_ID,
        )


def test_review_target_rejects_empty_reason(settings: Settings, sample_import: dict) -> None:
    service = ExternalDatasetSampleReviewService(settings)
    with pytest.raises(DatasetSampleReviewError):
        service.review_target(
            sample_import["public_id"],
            target_type="file",
            target_id="file-1",
            decision="accept",
            reason="   ",
            reviewer_admin_public_id=REVIEWER_ID,
        )


def test_derived_content_only_allowed_for_derived_revision_decisions(
    settings: Settings, sample_import: dict
) -> None:
    service = ExternalDatasetSampleReviewService(settings)
    with pytest.raises(DatasetSampleReviewError):
        service.review_target(
            sample_import["public_id"],
            target_type="record",
            target_id="record-1",
            decision="accept",
            reason="fine",
            reviewer_admin_public_id=REVIEWER_ID,
            derived_content_text="should not be allowed here",
        )


def test_redact_derived_copy_stores_derived_content_and_checksum(
    settings: Settings, sample_import: dict
) -> None:
    service = ExternalDatasetSampleReviewService(settings)
    review = service.review_target(
        sample_import["public_id"],
        target_type="record",
        target_id="record-1",
        decision="redact_derived_copy",
        reason="Redacted the email address found in this record",
        reviewer_admin_public_id=REVIEWER_ID,
        derived_content_text="Contact <EMAIL_REDACTED> for details.",
    )
    assert review["derived_content_text"] == "Contact <EMAIL_REDACTED> for details."
    assert review["derived_content_checksum"]


def test_review_issue_updates_the_issue_row_itself(settings: Settings, sample_import: dict) -> None:
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    issue = samples.add_record_issue(
        sample_import["public_id"],
        {"issue_category": "pii", "issue_type": "email_address", "status": "possible"},
    )
    service = ExternalDatasetSampleReviewService(settings)
    service.review_target(
        sample_import["public_id"],
        target_type="issue",
        target_id=issue["public_id"],
        decision="exclude",
        reason="Confirmed real PII, excluding this record",
        reviewer_admin_public_id=REVIEWER_ID,
    )
    refreshed = samples.get_record_issue(issue["public_id"])
    assert refreshed["reviewer_decision"] == "exclude"
    assert refreshed["reviewed_by"] == REVIEWER_ID


def test_review_target_records_an_event(settings: Settings, sample_import: dict) -> None:
    service = ExternalDatasetSampleReviewService(settings)
    service.review_target(
        sample_import["public_id"],
        target_type="file",
        target_id="file-1",
        decision="accept",
        reason="fine",
        reviewer_admin_public_id=REVIEWER_ID,
    )
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    events = samples.list_events(sample_import["public_id"])
    assert any(event["event_type"] == "review_recorded" for event in events)
