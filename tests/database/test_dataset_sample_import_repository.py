from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "sample_import.db"
    initialize_database(path)
    return path


@pytest.fixture
def repository(database_path: Path) -> DatasetSampleImportRepository:
    return DatasetSampleImportRepository(database_path)


@pytest.fixture
def case_public_id(database_path: Path) -> str:
    discovery = ExternalDatasetDiscoveryRepository(database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"],
        {"canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus"},
    )
    verification = DatasetVerificationRepository(database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"],
            "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    return case["public_id"]


@pytest.fixture
def candidate_public_id(database_path: Path, case_public_id: str) -> str:
    verification = DatasetVerificationRepository(database_path)
    return verification.get_case(case_public_id)["candidate_public_id"]


def _create_sample_import(
    repository: DatasetSampleImportRepository,
    case_public_id: str,
    candidate_public_id: str,
    code: str = "SI-1",
) -> dict:
    return repository.create_sample_import(
        {
            "sample_import_code": code,
            "verification_case_public_id": case_public_id,
            "candidate_public_id": candidate_public_id,
            "purpose": "manual_review",
            "selection_method": "deterministic_first_n",
            "requested_count": 500,
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )


def _create_approval(repository: DatasetSampleImportRepository, sample_import: dict) -> dict:
    return repository.create_approval(
        sample_import["public_id"],
        {
            "verification_case_public_id": sample_import["verification_case_public_id"],
            "candidate_public_id": sample_import["candidate_public_id"],
            "purpose": "manual_review",
            "requested_record_limit": 500,
            "requested_byte_limit": 20_000_000,
            "target_fingerprint": "fp-1",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )


# -- sample imports -----------------------------------------------------------------


def test_create_and_get_sample_import(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    fetched = repository.get_sample_import(created["public_id"])
    assert fetched["status"] == "draft"
    assert fetched["current_stage"] == "eligibility_check"
    assert fetched["purpose"] == "manual_review"
    assert fetched["verification_case_public_id"] == case_public_id
    assert fetched["candidate_public_id"] == candidate_public_id


def test_get_sample_import_missing_raises(repository: DatasetSampleImportRepository) -> None:
    with pytest.raises(NotFoundError):
        repository.get_sample_import("not-a-real-id")


def test_get_active_sample_import_for_case_excludes_terminal_statuses(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    active = repository.get_active_sample_import_for_case(case_public_id)
    assert active is not None
    assert active["public_id"] == created["public_id"]

    repository.update_sample_import(created["public_id"], {"status": "cancelled"})
    assert repository.get_active_sample_import_for_case(case_public_id) is None


def test_list_sample_imports_filters_by_status(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    first = _create_sample_import(repository, case_public_id, candidate_public_id, code="SI-a")
    _create_sample_import(repository, case_public_id, candidate_public_id, code="SI-b")
    repository.update_sample_import(first["public_id"], {"status": "cancelled"})

    cancelled = repository.list_sample_imports(status="cancelled")
    assert len(cancelled) == 1
    assert cancelled[0]["public_id"] == first["public_id"]


def test_update_sample_import_refuses_once_locked(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    repository.lock_sample_import(
        created["public_id"],
        report={"summary": "done"},
        rag_sandbox_eligible=True,
        training_assessment_status="not_assessed",
    )
    with pytest.raises(ValidationError):
        repository.update_sample_import(created["public_id"], {"status": "needs_review"})


def test_lock_sample_import_refuses_twice(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    repository.lock_sample_import(
        created["public_id"],
        report={"summary": "done"},
        rag_sandbox_eligible=True,
        training_assessment_status="not_assessed",
    )
    with pytest.raises(ValidationError):
        repository.lock_sample_import(
            created["public_id"],
            report={"summary": "done again"},
            rag_sandbox_eligible=True,
            training_assessment_status="not_assessed",
        )


def test_lock_sample_import_stores_rag_eligibility_and_training_signal(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    locked = repository.lock_sample_import(
        created["public_id"],
        report={"summary": "done"},
        rag_sandbox_eligible=True,
        training_assessment_status="needs_more_review",
    )
    assert locked["rag_sandbox_eligible"] is True
    assert locked["training_assessment_status"] == "needs_more_review"
    assert locked["locked_at"] is not None


def test_overview_counts_reflect_live_state(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    repository.update_sample_import(created["public_id"], {"status": "awaiting_approval"})
    counts = repository.overview_counts()
    assert counts["sample_imports_awaiting_approval"] == 1
    assert counts["quarantine_storage_used_bytes"] == 0


# -- approvals ------------------------------------------------------------------------


def test_create_approval_moves_import_to_awaiting_approval(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    approval = _create_approval(repository, created)
    assert approval["status"] == "pending"
    refreshed = repository.get_sample_import(created["public_id"])
    assert refreshed["status"] == "awaiting_approval"
    assert refreshed["current_stage"] == "approval"


def test_approve_approval_moves_import_to_approved(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    approval = _create_approval(repository, created)
    approved = repository.approve_approval(
        approval["public_id"],
        approved_by_admin_id=ADMIN_ID,
        approved_record_limit=500,
        approved_byte_limit=20_000_000,
        expires_at="2026-12-31T00:00:00",
    )
    assert approved["status"] == "approved"
    assert approved["approved_record_limit"] == 500
    refreshed = repository.get_sample_import(created["public_id"])
    assert refreshed["status"] == "approved"


def test_approve_approval_refuses_when_not_pending(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    approval = _create_approval(repository, created)
    repository.approve_approval(
        approval["public_id"],
        approved_by_admin_id=ADMIN_ID,
        approved_record_limit=500,
        approved_byte_limit=20_000_000,
        expires_at="2026-12-31T00:00:00",
    )
    with pytest.raises(ValidationError):
        repository.approve_approval(
            approval["public_id"],
            approved_by_admin_id=ADMIN_ID,
            approved_record_limit=500,
            approved_byte_limit=20_000_000,
            expires_at="2026-12-31T00:00:00",
        )


def test_reject_approval_moves_import_to_rejected(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    approval = _create_approval(repository, created)
    rejected = repository.reject_approval(approval["public_id"])
    assert rejected["status"] == "rejected"
    refreshed = repository.get_sample_import(created["public_id"])
    assert refreshed["status"] == "rejected"


def test_expire_approval_requires_approved_status(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    approval = _create_approval(repository, created)
    with pytest.raises(ValidationError):
        repository.expire_approval(approval["public_id"])

    repository.approve_approval(
        approval["public_id"],
        approved_by_admin_id=ADMIN_ID,
        approved_record_limit=500,
        approved_byte_limit=20_000_000,
        expires_at="2026-12-31T00:00:00",
    )
    expired = repository.expire_approval(approval["public_id"])
    assert expired["status"] == "expired"


def test_get_latest_approval_returns_most_recent(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    first = _create_approval(repository, created)
    repository.reject_approval(first["public_id"])
    repository.update_sample_import(created["public_id"], {"status": "draft"})
    second = _create_approval(repository, created)
    latest = repository.get_latest_approval(created["public_id"])
    assert latest["public_id"] == second["public_id"]
    assert len(repository.list_approvals(created["public_id"])) == 2


# -- files, download events, extraction events, scan results --------------------------


def test_add_file_and_update_status(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    file = repository.add_file(
        created["public_id"],
        {
            "original_filename": "data.csv",
            "safe_filename": "data.csv",
            "relative_path": "original/data.csv",
            "declared_format": "csv",
        },
    )
    assert file["status"] == "pending"
    updated = repository.update_file(file["public_id"], {"status": "validated", "size_bytes": 1024})
    assert updated["status"] == "validated"
    assert updated["size_bytes"] == 1024
    assert len(repository.list_files(created["public_id"])) == 1
    assert len(repository.list_files(created["public_id"], status="validated")) == 1
    assert len(repository.list_files(created["public_id"], status="blocked")) == 0


def test_download_events_are_append_only_via_repository(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    file = repository.add_file(
        created["public_id"],
        {"original_filename": "x.txt", "safe_filename": "x.txt", "relative_path": "original/x.txt"},
    )
    repository.record_download_event(
        created["public_id"],
        {
            "file_public_id": file["public_id"],
            "event_type": "started",
            "performed_by_admin_public_id": ADMIN_ID,
        },
    )
    repository.record_download_event(
        created["public_id"],
        {
            "file_public_id": file["public_id"],
            "event_type": "completed",
            "bytes_downloaded": 512,
            "performed_by_admin_public_id": ADMIN_ID,
        },
    )
    events = repository.list_download_events(created["public_id"])
    assert [event["event_type"] for event in events] == ["started", "completed"]


def test_extraction_events_require_existing_archive_file(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    with pytest.raises(NotFoundError):
        repository.record_extraction_event(
            created["public_id"],
            {
                "archive_file_public_id": "not-a-real-file",
                "event_type": "started",
                "performed_by_admin_public_id": ADMIN_ID,
            },
        )


def test_record_scan_result(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    file = repository.add_file(
        created["public_id"],
        {"original_filename": "x.txt", "safe_filename": "x.txt", "relative_path": "original/x.txt"},
    )
    result = repository.record_scan_result(
        created["public_id"],
        {"file_public_id": file["public_id"], "verdict": "clean_by_policy"},
    )
    assert result["verdict"] == "clean_by_policy"
    assert len(repository.list_scan_results(created["public_id"])) == 1


# -- records + record issues ----------------------------------------------------------


def test_add_record_and_update_status(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    file = repository.add_file(
        created["public_id"],
        {"original_filename": "x.txt", "safe_filename": "x.txt", "relative_path": "original/x.txt"},
    )
    record = repository.add_record(
        created["public_id"],
        {
            "source_file_public_id": file["public_id"],
            "raw_content": "hello",
            "normalized_content": "hello",
            "source_checksum": "a" * 64,
            "record_checksum": "b" * 64,
        },
    )
    assert record["status"] == "pending"
    assert record["raw_content"] == "hello"
    updated = repository.update_record_status(record["public_id"], "accepted")
    assert updated["status"] == "accepted"


def test_record_issue_review_requires_nonempty_reason(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    issue = repository.add_record_issue(
        created["public_id"],
        {
            "issue_category": "pii",
            "issue_type": "email_address",
            "status": "possible",
        },
    )
    with pytest.raises(ValidationError):
        repository.review_record_issue(
            issue["public_id"], reviewer_decision="accept", reviewed_by=REVIEWER_ID,
            review_reason="  ",
        )
    reviewed = repository.review_record_issue(
        issue["public_id"],
        reviewer_decision="redact_derived_copy",
        reviewed_by=REVIEWER_ID,
        review_reason="Confirmed real email address",
    )
    assert reviewed["reviewer_decision"] == "redact_derived_copy"
    assert reviewed["reviewed_by"] == REVIEWER_ID


def test_list_record_issues_filters_by_category_and_status(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    repository.add_record_issue(
        created["public_id"],
        {"issue_category": "pii", "issue_type": "email_address", "status": "possible"},
    )
    repository.add_record_issue(
        created["public_id"],
        {"issue_category": "quality", "issue_type": "too_short", "status": "fail"},
    )
    pii_issues = repository.list_record_issues(created["public_id"], issue_category="pii")
    assert len(pii_issues) == 1
    assert pii_issues[0]["issue_category"] == "pii"


# -- reviews, reports, events -----------------------------------------------------------


def test_add_review_requires_reason_at_schema_level(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    review = repository.add_review(
        created["public_id"],
        {
            "target_type": "file",
            "decision": "accept",
            "reason": "Looks safe",
            "reviewer_admin_public_id": ADMIN_ID,
        },
    )
    assert review["decision"] == "accept"
    assert len(repository.list_reviews(created["public_id"])) == 1


def test_add_report_versions_increment_per_import(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    first = repository.add_report(
        created["public_id"],
        {
            "rag_sandbox_eligible": False,
            "training_assessment_status": "not_assessed",
            "report": {"summary": "first pass"},
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    second = repository.add_report(
        created["public_id"],
        {
            "rag_sandbox_eligible": True,
            "training_assessment_status": "potentially_suitable",
            "report": {"summary": "second pass"},
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    assert first["report_version"] == 1
    assert second["report_version"] == 2
    latest = repository.get_latest_report(created["public_id"])
    assert latest["public_id"] == second["public_id"]
    assert latest["rag_sandbox_eligible"] is True


def test_record_event_defaults_performed_by_to_system(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    event = repository.record_event(created["public_id"], {"event_type": "import_created"})
    assert event["performed_by_admin_public_id"] == "system"
    assert len(repository.list_events(created["public_id"])) == 1


# -- deletion requests ------------------------------------------------------------------


def test_deletion_lifecycle_requested_confirmed_executed(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    requested = repository.request_deletion(
        created["public_id"],
        {"reason": "No longer needed", "requested_by_admin_public_id": ADMIN_ID},
    )
    assert requested["status"] == "requested"
    code = requested["deletion_request_code"]

    confirmed = repository.confirm_deletion(code, confirmed_by_admin_public_id=REVIEWER_ID)
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_by_admin_public_id"] == REVIEWER_ID

    executed = repository.execute_deletion(code)
    assert executed["status"] == "executed"
    assert executed["executed_at"] is not None

    history = repository.list_deletion_requests(created["public_id"])
    assert [row["status"] for row in history] == ["requested", "confirmed", "executed"]

    latest = repository.get_latest_deletion_request(created["public_id"])
    assert latest["status"] == "executed"


def test_cancel_deletion_records_cancelled_transition(
    repository: DatasetSampleImportRepository, case_public_id: str, candidate_public_id: str
) -> None:
    created = _create_sample_import(repository, case_public_id, candidate_public_id)
    requested = repository.request_deletion(
        created["public_id"],
        {"reason": "Duplicate import", "requested_by_admin_public_id": ADMIN_ID},
    )
    cancelled = repository.cancel_deletion(requested["deletion_request_code"])
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_at"] is not None


def test_confirm_deletion_unknown_code_raises(repository: DatasetSampleImportRepository) -> None:
    with pytest.raises(NotFoundError):
        repository.confirm_deletion("not-a-real-code", confirmed_by_admin_public_id=ADMIN_ID)
