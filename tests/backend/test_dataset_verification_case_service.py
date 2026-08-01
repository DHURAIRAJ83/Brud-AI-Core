from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.dataset_verification_case_service import (
    DatasetVerificationCaseError,
    ExternalDatasetVerificationService,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "verification.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def candidate_public_id(settings: Settings) -> str:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus"}
    )
    return candidate["public_id"]


def test_create_case_defaults(settings: Settings, candidate_public_id: str) -> None:
    service = ExternalDatasetVerificationService(settings)
    case = service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)
    assert case["status"] == "draft"
    assert case["candidate_public_id"] == candidate_public_id
    assert case["verification_code"].startswith("VC-")

    events = service.repository.list_events(case["public_id"])
    assert any(e["event_type"] == "case_created" for e in events)


def test_create_case_blocks_duplicate_active_case_for_same_candidate(
    settings: Settings, candidate_public_id: str
) -> None:
    service = ExternalDatasetVerificationService(settings)
    service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)
    with pytest.raises(DatasetVerificationCaseError):
        service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)


def test_create_case_allows_new_case_after_prior_one_terminal(
    settings: Settings, candidate_public_id: str
) -> None:
    service = ExternalDatasetVerificationService(settings)
    first = service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)
    service.cancel(first["public_id"], admin_id=ADMIN_ID)
    second = service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)
    assert second["public_id"] != first["public_id"]


def test_create_case_force_new_version_bypasses_active_case_guard(
    settings: Settings, candidate_public_id: str
) -> None:
    service = ExternalDatasetVerificationService(settings)
    first = service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)
    second = service.create_case(
        candidate_public_id=candidate_public_id, admin_id=ADMIN_ID, force_new_version=True
    )
    assert second["public_id"] != first["public_id"]


def test_start_transitions_from_draft_to_collecting_evidence(
    settings: Settings, candidate_public_id: str
) -> None:
    service = ExternalDatasetVerificationService(settings)
    case = service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)
    started = service.start(case["public_id"], admin_id=ADMIN_ID)
    assert started["status"] == "collecting_evidence"
    assert started["started_at"] is not None


def test_start_refuses_when_not_draft(settings: Settings, candidate_public_id: str) -> None:
    service = ExternalDatasetVerificationService(settings)
    case = service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)
    service.start(case["public_id"], admin_id=ADMIN_ID)
    with pytest.raises(DatasetVerificationCaseError):
        service.start(case["public_id"], admin_id=ADMIN_ID)


def test_cancel_sets_status_and_timestamp(settings: Settings, candidate_public_id: str) -> None:
    service = ExternalDatasetVerificationService(settings)
    case = service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)
    cancelled = service.cancel(case["public_id"], admin_id=ADMIN_ID)
    assert cancelled["status"] == "cancelled"
    assert cancelled["cancelled_at"] is not None


def test_cancel_refuses_on_finalized_case(settings: Settings, candidate_public_id: str) -> None:
    service = ExternalDatasetVerificationService(settings)
    case = service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)
    service.repository.lock_case(case["public_id"], {})
    with pytest.raises(DatasetVerificationCaseError):
        service.cancel(case["public_id"], admin_id=ADMIN_ID)


def test_list_and_get_case(settings: Settings, candidate_public_id: str) -> None:
    service = ExternalDatasetVerificationService(settings)
    case = service.create_case(candidate_public_id=candidate_public_id, admin_id=ADMIN_ID)
    assert service.get_case(case["public_id"])["public_id"] == case["public_id"]
    listed = service.list_cases(candidate_public_id=candidate_public_id)
    assert [c["public_id"] for c in listed] == [case["public_id"]]
