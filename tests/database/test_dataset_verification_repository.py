from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "verification.db"
    initialize_database(path)
    return path


@pytest.fixture
def repository(database_path: Path) -> DatasetVerificationRepository:
    return DatasetVerificationRepository(database_path)


@pytest.fixture
def candidate_public_id(database_path: Path) -> str:
    discovery = ExternalDatasetDiscoveryRepository(database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"],
        {"canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus"},
    )
    return candidate["public_id"]


def _create_case(repository: DatasetVerificationRepository, candidate_public_id: str, code="VC-1"):
    return repository.create_case(
        {
            "candidate_public_id": candidate_public_id,
            "verification_code": code,
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )


def _add_evidence(
    repository: DatasetVerificationRepository, case_public_id, candidate_public_id, **overrides
):
    values = {
        "candidate_public_id": candidate_public_id,
        "evidence_type": "licence_file",
        "authority_level": "primary",
        "content_type": "text/plain",
        "content_checksum": "a" * 64,
        "created_by_admin_public_id": ADMIN_ID,
    }
    values.update(overrides)
    return repository.add_evidence_snapshot(case_public_id, values)


# -- verification cases -------------------------------------------------------


def test_create_and_get_case_defaults(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    assert case["status"] == "draft"
    assert case["identity_status"] == "not_verified"
    assert case["evidence_status"] == "not_started"
    assert case["licence_status"] == "unknown"
    assert case["locked_at"] is None
    assert case["candidate_public_id"] == candidate_public_id

    fetched = repository.get_case(case["public_id"])
    assert fetched == case

    with pytest.raises(NotFoundError):
        repository.get_case("does-not-exist")


def test_get_case_by_code(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id, code="by-code")
    found = repository.get_case_by_code("by-code")
    assert found["public_id"] == case["public_id"]
    assert repository.get_case_by_code("missing-code") is None


def test_create_case_copies_declared_licence_from_candidate(
    database_path: Path, repository
) -> None:
    discovery = ExternalDatasetDiscoveryRepository(database_path)
    session = discovery.create_session(
        {"session_code": "session-licence", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"],
        {
            "canonical_name": "Tamil ASR",
            "normalized_name": "tamil asr",
            "declared_licence": "CC-BY-4.0",
        },
    )
    case = _create_case(repository, candidate["public_id"])
    assert case["declared_licence"] == "CC-BY-4.0"
    assert case["normalized_licence_identifier"] is None


def test_create_case_rejects_unknown_candidate(repository) -> None:
    with pytest.raises(NotFoundError):
        repository.create_case(
            {
                "candidate_public_id": "does-not-exist",
                "verification_code": "VC-bad",
                "requested_by_admin_public_id": ADMIN_ID,
            }
        )


def test_get_active_case_for_candidate_excludes_terminal_statuses(
    repository, candidate_public_id
) -> None:
    case = _create_case(repository, candidate_public_id)
    active = repository.get_active_case_for_candidate(candidate_public_id)
    assert active["public_id"] == case["public_id"]

    repository.update_case(case["public_id"], {"status": "cancelled"})
    assert repository.get_active_case_for_candidate(candidate_public_id) is None


def test_list_cases_filters(repository, candidate_public_id) -> None:
    c1 = _create_case(repository, candidate_public_id, code="c1")
    c2 = _create_case(repository, candidate_public_id, code="c2")
    repository.update_case(c2["public_id"], {"status": "in_review"})

    all_items = repository.list_cases(limit=50)
    assert {c1["public_id"], c2["public_id"]} <= {item["public_id"] for item in all_items}

    in_review_only = repository.list_cases(status="in_review")
    assert [item["public_id"] for item in in_review_only] == [c2["public_id"]]

    by_candidate = repository.list_cases(candidate_public_id=candidate_public_id)
    assert {c1["public_id"], c2["public_id"]} <= {item["public_id"] for item in by_candidate}


def test_lock_case_freezes_report_and_refuses_twice(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    locked = repository.lock_case(case["public_id"], {"summary": "finalized"})
    assert locked["locked_at"] is not None
    assert locked["report"] == {"summary": "finalized"}

    with pytest.raises(ValidationError):
        repository.lock_case(case["public_id"], {"summary": "again"})


def test_update_case_refused_once_locked(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    repository.lock_case(case["public_id"], {})
    with pytest.raises(ValidationError):
        repository.update_case(case["public_id"], {"status": "verified"})


# -- evidence snapshots --------------------------------------------------------


def test_add_and_get_evidence_snapshot(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    snapshot = _add_evidence(repository, case["public_id"], candidate_public_id)
    assert snapshot["is_current"] is True
    assert snapshot["ocr_derived"] is False
    assert snapshot["verification_case_public_id"] == case["public_id"]

    fetched = repository.get_evidence_snapshot(snapshot["public_id"])
    assert fetched == snapshot


def test_evidence_snapshot_supersede_flips_is_current(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    old = _add_evidence(
        repository, case["public_id"], candidate_public_id, content_checksum="a" * 64
    )
    new = _add_evidence(
        repository,
        case["public_id"],
        candidate_public_id,
        content_checksum="b" * 64,
        supersedes_evidence_public_id=old["public_id"],
    )
    assert repository.get_evidence_snapshot(old["public_id"])["is_current"] is False
    assert new["is_current"] is True
    assert new["supersedes_evidence_public_id"] == old["public_id"]


def test_list_evidence_snapshots_filters(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    licence = _add_evidence(
        repository, case["public_id"], candidate_public_id,
        evidence_type="licence_file", content_checksum="a" * 64,
    )
    _add_evidence(
        repository, case["public_id"], candidate_public_id,
        evidence_type="readme", authority_level="secondary", content_checksum="b" * 64,
    )

    by_type = repository.list_evidence_snapshots(case["public_id"], evidence_type="licence_file")
    assert [row["public_id"] for row in by_type] == [licence["public_id"]]

    all_current = repository.list_evidence_snapshots(case["public_id"], current_only=True)
    assert len(all_current) == 2


def test_add_evidence_snapshot_refused_once_locked(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    repository.lock_case(case["public_id"], {})
    with pytest.raises(ValidationError):
        _add_evidence(repository, case["public_id"], candidate_public_id)


# -- evidence links -------------------------------------------------------------


def test_add_evidence_link_and_list_for_entity_and_snapshot(
    repository, candidate_public_id
) -> None:
    case = _create_case(repository, candidate_public_id)
    snapshot = _add_evidence(repository, case["public_id"], candidate_public_id)
    link = repository.add_evidence_link(
        snapshot["public_id"], linked_entity_type="identity_check", linked_entity_id=42
    )
    assert link["evidence_snapshot_public_id"] == snapshot["public_id"]

    by_entity = repository.list_evidence_links_for_entity("identity_check", 42)
    assert [row["public_id"] for row in by_entity] == [link["public_id"]]

    by_snapshot = repository.list_evidence_links_for_snapshot(snapshot["public_id"])
    assert [row["public_id"] for row in by_snapshot] == [link["public_id"]]


def test_add_evidence_link_is_idempotent_for_same_role(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    snapshot = _add_evidence(repository, case["public_id"], candidate_public_id)
    repository.add_evidence_link(
        snapshot["public_id"], linked_entity_type="identity_check", linked_entity_id=1
    )
    repository.add_evidence_link(
        snapshot["public_id"], linked_entity_type="identity_check", linked_entity_id=1
    )
    assert len(repository.list_evidence_links_for_snapshot(snapshot["public_id"])) == 1


# -- identity checks ------------------------------------------------------------


def test_add_and_list_identity_checks(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    check = repository.add_identity_check(
        case["public_id"],
        {
            "candidate_public_id": candidate_public_id,
            "signal_type": "official_domain",
            "expected_value": "huggingface.co",
            "observed_value": "huggingface.co",
            "matched": True,
            "reason": "exact domain match",
        },
    )
    assert check["matched"] is True
    listed = repository.list_identity_checks(case["public_id"])
    assert [row["public_id"] for row in listed] == [check["public_id"]]


def test_add_identity_check_refused_once_locked(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    repository.lock_case(case["public_id"], {})
    with pytest.raises(ValidationError):
        repository.add_identity_check(
            case["public_id"],
            {
                "candidate_public_id": candidate_public_id,
                "signal_type": "dataset_name",
                "reason": "n/a",
            },
        )


# -- permission assessments -----------------------------------------------------


def test_assess_permission_upserts_and_rejects_admin_only_status(
    repository, candidate_public_id
) -> None:
    case = _create_case(repository, candidate_public_id)
    first = repository.assess_permission(
        case["public_id"], "training_use",
        {"candidate_public_id": candidate_public_id, "status": "unknown"},
    )
    assert first["status"] == "unknown"

    second = repository.assess_permission(
        case["public_id"], "training_use",
        {"candidate_public_id": candidate_public_id, "status": "needs_legal_review"},
    )
    assert second["status"] == "needs_legal_review"
    assert second["public_id"] == first["public_id"]
    assert len(repository.list_permission_assessments(case["public_id"])) == 1

    with pytest.raises(ValidationError):
        repository.assess_permission(
            case["public_id"], "commercial_use",
            {"candidate_public_id": candidate_public_id, "status": "approved"},
        )


def test_review_permission_requires_prior_assessment(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    with pytest.raises(NotFoundError):
        repository.review_permission(
            case["public_id"], "training_use",
            status="approved", reviewed_by=REVIEWER_ID, reason="Evidence confirmed",
        )


def test_review_permission_rejects_non_admin_only_status(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    repository.assess_permission(
        case["public_id"], "training_use",
        {"candidate_public_id": candidate_public_id, "status": "unknown"},
    )
    with pytest.raises(ValidationError):
        repository.review_permission(
            case["public_id"], "training_use",
            status="likely_allowed", reviewed_by=REVIEWER_ID, reason="not admin-only",
        )


def test_review_permission_rejects_empty_reason(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    repository.assess_permission(
        case["public_id"], "training_use",
        {"candidate_public_id": candidate_public_id, "status": "unknown"},
    )
    with pytest.raises(ValidationError):
        repository.review_permission(
            case["public_id"], "training_use",
            status="approved", reviewed_by=REVIEWER_ID, reason="   ",
        )


def test_review_permission_succeeds_and_writes_append_only_review(
    repository, candidate_public_id
) -> None:
    case = _create_case(repository, candidate_public_id)
    repository.assess_permission(
        case["public_id"], "training_use",
        {"candidate_public_id": candidate_public_id, "status": "needs_legal_review"},
    )
    reviewed = repository.review_permission(
        case["public_id"], "training_use",
        status="approved_with_conditions", reviewed_by=REVIEWER_ID,
        reason="Licence file confirms CC-BY-4.0, attribution required",
        conditions={"attribution": "required"},
    )
    assert reviewed["status"] == "approved_with_conditions"
    assert reviewed["reviewed_by"] == REVIEWER_ID
    assert reviewed["conditions"] == {"attribution": "required"}

    reviews = repository.list_reviews(case["public_id"])
    assert len(reviews) == 1
    assert reviews[0]["decision"] == "approved_with_conditions"
    assert reviews[0]["reviewer_admin_public_id"] == REVIEWER_ID


# -- verification events ---------------------------------------------------------


def test_record_and_list_events(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    event = repository.record_event(
        case["public_id"],
        {"event_type": "case_created", "performed_by_admin_public_id": ADMIN_ID},
    )
    fetched = repository.get_event(event["public_id"])
    assert fetched == event
    assert [row["public_id"] for row in repository.list_events(case["public_id"])] == [
        event["public_id"]
    ]


def test_conflict_detected_event_carries_severity_and_resolution(
    repository, candidate_public_id
) -> None:
    case = _create_case(repository, candidate_public_id)
    repository.record_event(
        case["public_id"],
        {"event_type": "case_created", "performed_by_admin_public_id": ADMIN_ID},
    )
    conflict = repository.record_event(
        case["public_id"],
        {
            "event_type": "conflict_detected",
            "conflict_type": "declared_vs_licence_file",
            "conflict_severity": "blocking",
            "resolution_status": "unresolved",
            "performed_by_admin_public_id": ADMIN_ID,
        },
    )
    conflicts_only = repository.list_conflict_events(case["public_id"])
    assert [row["public_id"] for row in conflicts_only] == [conflict["public_id"]]
    assert conflicts_only[0]["conflict_severity"] == "blocking"


# -- withdrawal notices -----------------------------------------------------------


def test_record_and_list_withdrawal_notices(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    notice = repository.record_withdrawal_notice(
        case["public_id"],
        {
            "candidate_public_id": candidate_public_id,
            "notice_type": "licence_changed",
            "recorded_by_admin_public_id": ADMIN_ID,
        },
    )
    assert notice["impact_status"] == "pending_assessment"
    fetched = repository.get_withdrawal_notice(notice["public_id"])
    assert fetched == notice
    assert [row["public_id"] for row in repository.list_withdrawal_notices(case["public_id"])] == [
        notice["public_id"]
    ]


# -- upstream sources ---------------------------------------------------------------


def test_add_update_and_list_upstream_sources(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    upstream = repository.add_upstream_source(
        case["public_id"],
        {
            "candidate_public_id": candidate_public_id,
            "upstream_name": "Common Voice",
            "relationship_type": "aggregated_from",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    assert upstream["verification_status"] == "not_verified"
    assert repository.unresolved_upstream_exists(case["public_id"]) is True

    updated = repository.update_upstream_source(
        upstream["public_id"], {"verification_status": "verified"}
    )
    assert updated["verification_status"] == "verified"
    assert repository.unresolved_upstream_exists(case["public_id"]) is False

    listed = repository.list_upstream_sources(case["public_id"])
    assert [row["public_id"] for row in listed] == [upstream["public_id"]]


def test_upstream_source_refused_once_locked(repository, candidate_public_id) -> None:
    case = _create_case(repository, candidate_public_id)
    upstream = repository.add_upstream_source(
        case["public_id"],
        {
            "candidate_public_id": candidate_public_id,
            "upstream_name": "Common Voice",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    repository.lock_case(case["public_id"], {})
    with pytest.raises(ValidationError):
        repository.update_upstream_source(
            upstream["public_id"], {"verification_status": "verified"}
        )
    with pytest.raises(ValidationError):
        repository.add_upstream_source(
            case["public_id"],
            {
                "candidate_public_id": candidate_public_id,
                "upstream_name": "Another Corpus",
                "created_by_admin_public_id": ADMIN_ID,
            },
        )


# -- reverification's 3 deliberate exceptions to "immutable once locked" -------


def test_add_evidence_snapshot_allow_locked_case_bypasses_lock(
    repository, candidate_public_id
) -> None:
    case = _create_case(repository, candidate_public_id)
    repository.lock_case(case["public_id"], {})
    snapshot = repository.add_evidence_snapshot(
        case["public_id"],
        {
            "candidate_public_id": candidate_public_id,
            "evidence_type": "licence_file",
            "authority_level": "primary",
            "content_type": "text/plain",
            "content_checksum": "a" * 64,
            "created_by_admin_public_id": ADMIN_ID,
        },
        allow_locked_case=True,
    )
    assert snapshot["verification_case_public_id"] == case["public_id"]

    with pytest.raises(ValidationError):
        _add_evidence(repository, case["public_id"], candidate_public_id)


def test_update_case_reverification_fields_bypasses_lock_but_only_for_whitelisted_keys(
    repository, candidate_public_id
) -> None:
    case = _create_case(repository, candidate_public_id)
    repository.lock_case(case["public_id"], {})
    updated = repository.update_case_reverification_fields(
        case["public_id"], {"verification_expiry_status": "source_changed"}
    )
    assert updated["verification_expiry_status"] == "source_changed"

    with pytest.raises(ValidationError):
        repository.update_case_reverification_fields(case["public_id"], {"status": "verified"})


def test_demote_permission_status_bypasses_lock_but_rejects_admin_only_status(
    repository, candidate_public_id
) -> None:
    case = _create_case(repository, candidate_public_id)
    repository.assess_permission(
        case["public_id"], "training_use",
        {"candidate_public_id": candidate_public_id, "status": "needs_legal_review"},
    )
    repository.review_permission(
        case["public_id"], "training_use",
        status="approved", reviewed_by=REVIEWER_ID, reason="Licence file confirms CC-BY-4.0",
    )
    repository.lock_case(case["public_id"], {})

    demoted = repository.demote_permission_status(
        case["public_id"], "training_use",
        new_status="needs_legal_review", reason="evidence checksum changed on refresh",
    )
    assert demoted["status"] == "needs_legal_review"

    with pytest.raises(ValidationError):
        repository.demote_permission_status(
            case["public_id"], "training_use", new_status="approved", reason="not allowed"
        )
