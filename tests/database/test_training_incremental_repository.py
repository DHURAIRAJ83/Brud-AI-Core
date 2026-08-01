import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.database.repositories.training_incremental import TrainingIncrementalRepository

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "training_incremental.db"
    initialize_database(path)
    return path


@pytest.fixture
def repository(database_path: Path) -> TrainingIncrementalRepository:
    return TrainingIncrementalRepository(database_path)


@pytest.fixture
def verification_case_public_id(database_path: Path) -> str:
    discovery = ExternalDatasetDiscoveryRepository(database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"], {"canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus"}
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


def _create_assessment(
    repository: TrainingIncrementalRepository, verification_case_public_id: str
) -> dict:
    return repository.create_assessment(
        {
            "assessment_code": "TDA-1",
            "verification_case_public_id": verification_case_public_id,
            "created_by_admin_public_id": ADMIN_ID,
        }
    )


def _insert_dataset_version(database_path: Path, *, name: str = "phase14-test") -> int:
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (str(uuid4()), name, "v1", "ready", "chk-dataset-version"),
        )
        connection.commit()
        return connection.execute(
            "SELECT id FROM dataset_versions WHERE name=?", (name,)
        ).fetchone()[0]


def _dataset_version_public_id(database_path: Path, dataset_version_id: int) -> str:
    with sqlite3.connect(database_path) as connection:
        return connection.execute(
            "SELECT public_id FROM dataset_versions WHERE id=?", (dataset_version_id,)
        ).fetchone()[0]


# -- assessments -----------------------------------------------------------------------


def test_create_and_get_assessment(
    repository: TrainingIncrementalRepository, verification_case_public_id: str
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    assert assessment["status"] == "not_assessed"
    assert assessment["current_stage"] == "lineage_check"
    fetched = repository.get_assessment(assessment["public_id"])
    assert fetched["assessment_code"] == "TDA-1"


def test_get_assessment_missing_raises(repository: TrainingIncrementalRepository) -> None:
    with pytest.raises(NotFoundError):
        repository.get_assessment("does-not-exist")


def test_list_assessments_filters_by_status(
    repository: TrainingIncrementalRepository, verification_case_public_id: str
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    repository.update_assessment(assessment["public_id"], {"status": "assessing"})
    matches = repository.list_assessments(status="assessing")
    assert any(row["public_id"] == assessment["public_id"] for row in matches)
    assert not repository.list_assessments(status="assessed")


def test_overview_counts_reflect_live_state(
    repository: TrainingIncrementalRepository, verification_case_public_id: str
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    repository.update_assessment(assessment["public_id"], {"status": "assessed"})
    counts = repository.overview_counts()
    assert counts["training_assessments_awaiting_review"] >= 1


# -- assessment items and candidates -----------------------------------------------------


def test_add_item_and_add_candidate(
    repository: TrainingIncrementalRepository, verification_case_public_id: str
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    item = repository.add_item(
        assessment["public_id"],
        {
            "record_category": "instruction_response",
            "suitability_status": "suitable_for_sft",
            "reason": "clean instruction/response pair",
        },
    )
    assert item["suitability_status"] == "suitable_for_sft"

    candidate = repository.add_candidate(
        item["public_id"],
        {
            "transformation_type": "instruction_response_pair",
            "prompt_text": "தமிழ் என்றால் என்ன?",
            "assistant_text": "தமிழ் ஒரு திராவிட மொழி.",
            "language": "tamil",
            "source_checksum": "chk-source-1",
            "candidate_checksum": "chk-candidate-1",
        },
    )
    assert candidate["review_status"] == "pending_review"
    assert len(repository.list_candidates(assessment_public_id=assessment["public_id"])) == 1

    reviewed = repository.review_candidate(
        candidate["public_id"], review_status="approved", reviewed_by=ADMIN_ID
    )
    assert reviewed["review_status"] == "approved"
    assert reviewed["reviewed_by"] == ADMIN_ID


def test_items_are_append_only_at_sql_level(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    item = repository.add_item(
        assessment["public_id"], {"record_category": "grammar", "reason": "x"}
    )
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE training_data_assessment_items SET reason='tampered' WHERE public_id=?",
                (item["public_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM training_data_assessment_items WHERE public_id=?",
                (item["public_id"],),
            )


def test_add_revision_and_list(
    repository: TrainingIncrementalRepository, verification_case_public_id: str
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    item = repository.add_item(
        assessment["public_id"], {"record_category": "correction_pair", "reason": "x"}
    )
    candidate = repository.add_candidate(
        item["public_id"],
        {
            "transformation_type": "correction_pair", "source_checksum": "s1",
            "candidate_checksum": "c1",
        },
    )
    revision = repository.add_revision(
        candidate["public_id"],
        {
            "decision": "needs_revision", "reason": "ambiguous Tamil correction",
            "reviewer_admin_public_id": ADMIN_ID,
        },
    )
    assert revision["decision"] == "needs_revision"
    assert len(repository.list_revisions(candidate["public_id"])) == 1


# -- replay plans -----------------------------------------------------------------------


def test_create_replay_plan(
    repository: TrainingIncrementalRepository, verification_case_public_id: str
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    plan = repository.create_replay_plan(
        assessment["public_id"],
        {
            "new_record_count": 320, "replay_record_count": 100,
            "new_data_ratio": 0.76, "replay_data_ratio": 0.24,
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    assert plan["new_record_count"] == 320
    assert len(repository.list_replay_plans(assessment["public_id"])) == 1


def test_replay_plans_are_append_only(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    plan = repository.create_replay_plan(
        assessment["public_id"],
        {
            "new_record_count": 1, "replay_record_count": 1, "new_data_ratio": 0.5,
            "replay_data_ratio": 0.5, "created_by_admin_public_id": ADMIN_ID,
        },
    )
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM training_replay_plans WHERE public_id=?", (plan["public_id"],)
            )


# -- dataset promotion requests -----------------------------------------------------------


def test_promotion_request_lifecycle(
    repository: TrainingIncrementalRepository, verification_case_public_id: str
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    request = repository.create_promotion_request(
        assessment["public_id"], {"requested_by_admin_public_id": ADMIN_ID}
    )
    assert request["status"] == "draft"
    approved = repository.approve_promotion_request(
        request["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None,
        target_fingerprint="fp-1",
    )
    assert approved["status"] == "approved"
    latest = repository.get_latest_promotion_request(assessment["public_id"])
    assert latest["public_id"] == request["public_id"]


def test_promotion_request_immutable_once_approved_at_sql_level(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    request = repository.create_promotion_request(
        assessment["public_id"], {"requested_by_admin_public_id": ADMIN_ID}
    )
    repository.approve_promotion_request(
        request["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None,
        target_fingerprint="fp-1",
    )
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE training_dataset_promotion_requests SET target_fingerprint='x' "
                "WHERE public_id=?",
                (request["public_id"],),
            )
    # But progressing to building/ready is still permitted.
    updated = repository.update_promotion_request(request["public_id"], {"status": "building"})
    assert updated["status"] == "building"


# -- run requests / approvals / runs -------------------------------------------------------


def test_run_request_and_approval_lifecycle(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    promotion = repository.create_promotion_request(
        assessment["public_id"], {"requested_by_admin_public_id": ADMIN_ID}
    )
    dataset_version_id = _insert_dataset_version(database_path)
    dataset_version_public_id = _dataset_version_public_id(database_path, dataset_version_id)

    run_request = repository.create_run_request(
        promotion["public_id"],
        {
            "dataset_version_public_id": dataset_version_public_id,
            "training_strategy": "incremental_sft",
            "configuration_checksum": "chk-config",
            "resource_preview_checksum": "chk-resource",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    assert run_request["status"] == "draft"
    assert run_request["dataset_version_public_id"] == dataset_version_public_id

    approval = repository.create_run_approval(
        run_request["public_id"],
        {"target_fingerprint": "fp-run-1", "requested_by_admin_public_id": ADMIN_ID},
    )
    assert approval["status"] == "pending"
    approved = repository.approve_run_approval(
        approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
    )
    assert approved["status"] == "approved"
    assert repository.get_latest_run_approval(run_request["public_id"])["public_id"] == (
        approval["public_id"]
    )

    with pytest.raises(ValidationError):
        repository.approve_run_approval(
            approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
        )


def test_run_approval_immutable_once_approved(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    promotion = repository.create_promotion_request(
        assessment["public_id"], {"requested_by_admin_public_id": ADMIN_ID}
    )
    dataset_version_id = _insert_dataset_version(database_path)
    dataset_version_public_id = _dataset_version_public_id(database_path, dataset_version_id)
    run_request = repository.create_run_request(
        promotion["public_id"],
        {
            "dataset_version_public_id": dataset_version_public_id,
            "training_strategy": "continued_pretraining",
            "configuration_checksum": "chk-config",
            "resource_preview_checksum": "chk-resource",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    approval = repository.create_run_approval(
        run_request["public_id"],
        {"target_fingerprint": "fp-run-2", "requested_by_admin_public_id": ADMIN_ID},
    )
    repository.approve_run_approval(
        approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
    )
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE incremental_training_run_approvals SET target_fingerprint='x' "
                "WHERE public_id=?",
                (approval["public_id"],),
            )


def test_create_run_and_update(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> None:
    assessment = _create_assessment(repository, verification_case_public_id)
    promotion = repository.create_promotion_request(
        assessment["public_id"], {"requested_by_admin_public_id": ADMIN_ID}
    )
    dataset_version_id = _insert_dataset_version(database_path)
    dataset_version_public_id = _dataset_version_public_id(database_path, dataset_version_id)
    run_request = repository.create_run_request(
        promotion["public_id"],
        {
            "dataset_version_public_id": dataset_version_public_id,
            "training_strategy": "incremental_sft",
            "configuration_checksum": "chk-config",
            "resource_preview_checksum": "chk-resource",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    approval = repository.create_run_approval(
        run_request["public_id"],
        {"target_fingerprint": "fp-run-3", "requested_by_admin_public_id": ADMIN_ID},
    )
    repository.approve_run_approval(
        approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
    )
    run = repository.create_run(
        run_request["public_id"],
        {
            "run_approval_public_id": approval["public_id"],
            "underlying_run_kind": "instruction_tuning_run",
            "underlying_run_public_id": "itr-1",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    assert run["status"] == "queued"
    updated = repository.update_run(run["public_id"], {"status": "running", "current_epoch": 1})
    assert updated["status"] == "running"
    assert updated["current_epoch"] == 1

    event = repository.record_run_event(run["public_id"], {"event_type": "run_started"})
    assert event["event_type"] == "run_started"
    assert len(repository.list_run_events(run["public_id"])) == 1


def _build_run(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> dict:
    assessment = _create_assessment(repository, verification_case_public_id)
    promotion = repository.create_promotion_request(
        assessment["public_id"], {"requested_by_admin_public_id": ADMIN_ID}
    )
    dataset_version_id = _insert_dataset_version(database_path, name=f"phase14-{uuid4().hex[:8]}")
    dataset_version_public_id = _dataset_version_public_id(database_path, dataset_version_id)
    run_request = repository.create_run_request(
        promotion["public_id"],
        {
            "dataset_version_public_id": dataset_version_public_id,
            "training_strategy": "incremental_sft",
            "configuration_checksum": "chk-config",
            "resource_preview_checksum": "chk-resource",
            "requested_by_admin_public_id": ADMIN_ID,
        },
    )
    approval = repository.create_run_approval(
        run_request["public_id"],
        {"target_fingerprint": "fp-run", "requested_by_admin_public_id": ADMIN_ID},
    )
    repository.approve_run_approval(
        approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
    )
    return repository.create_run(
        run_request["public_id"],
        {
            "run_approval_public_id": approval["public_id"],
            "underlying_run_kind": "instruction_tuning_run",
            "underlying_run_public_id": "itr-x",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )


# -- checkpoints / evaluations / comparisons / human reviews -------------------------------


def test_checkpoint_lifecycle_and_mutability_window(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> None:
    run = _build_run(repository, database_path, verification_case_public_id)
    checkpoint = repository.add_checkpoint(
        run["public_id"],
        {"underlying_checkpoint_public_id": "ckpt-1", "epoch": 1, "step": 100},
    )
    assert checkpoint["status"] == "created"
    verified = repository.update_checkpoint_status(checkpoint["public_id"], "verified")
    assert verified["status"] == "verified"
    evaluated = repository.update_checkpoint_status(checkpoint["public_id"], "evaluated")
    assert evaluated["status"] == "evaluated"
    # Once evaluated, status may still progress forward to an acceptance
    # decision (accepted_candidate/rejected/superseded) -- that transition
    # is what IncrementalTrainingCheckpointAcceptanceService performs --
    # but it can never move backward or change lineage.
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE incremental_training_checkpoints SET status='verified' "
                "WHERE public_id=?",
                (checkpoint["public_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE incremental_training_checkpoints SET "
                "underlying_checkpoint_public_id='ckpt-2' WHERE public_id=?",
                (checkpoint["public_id"],),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM incremental_training_checkpoints WHERE public_id=?",
                (checkpoint["public_id"],),
            )
    accepted = repository.update_checkpoint_status(checkpoint["public_id"], "accepted_candidate")
    assert accepted["status"] == "accepted_candidate"
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE incremental_training_checkpoints SET status='rejected' "
                "WHERE public_id=?",
                (checkpoint["public_id"],),
            )


def test_evaluation_comparison_and_human_review(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> None:
    run = _build_run(repository, database_path, verification_case_public_id)
    checkpoint = repository.add_checkpoint(
        run["public_id"], {"underlying_checkpoint_public_id": "ckpt-2"}
    )
    evaluation = repository.add_evaluation(
        checkpoint["public_id"],
        {"evaluation_type": "tamil_language_quality", "result_status": "pass"},
    )
    assert evaluation["automated"] is True
    assert len(repository.list_evaluations(checkpoint["public_id"])) == 1

    comparison = repository.add_comparison(
        checkpoint["public_id"],
        {
            "comparison_type": "forgetting_check", "dimension": "tamil_baseline",
            "result_status": "unchanged",
        },
    )
    assert comparison["result_status"] == "unchanged"
    assert len(repository.list_comparisons(checkpoint["public_id"])) == 1

    review = repository.add_human_review(
        checkpoint["public_id"],
        {"decision": "pass", "tamil_fluency": True, "reviewer_admin_public_id": ADMIN_ID},
    )
    assert review["decision"] == "pass"
    assert review["tamil_fluency"] is True
    assert len(repository.list_human_reviews(checkpoint["public_id"])) == 1


# -- reports and acceptances -----------------------------------------------------------------


def test_report_versions_increment_and_are_immutable(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> None:
    run = _build_run(repository, database_path, verification_case_public_id)
    first = repository.add_report(
        run["public_id"],
        {
            "report": {"summary": "v1"}, "report_checksum_sha256": "chk-1",
            "checkpoint_recommendation": "needs_more_evaluation",
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    second = repository.add_report(
        run["public_id"],
        {
            "report": {"summary": "v2"}, "report_checksum_sha256": "chk-2",
            "checkpoint_recommendation": "accept_candidate",
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    assert first["report_version"] == 1
    assert second["report_version"] == 2
    assert repository.get_latest_report(run["public_id"])["public_id"] == second["public_id"]
    assert len(repository.list_reports(run["public_id"])) == 2
    with sqlite3.connect(database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE incremental_training_reports SET report_checksum_sha256='x' "
                "WHERE public_id=?",
                (second["public_id"],),
            )


def test_checkpoint_acceptance_lifecycle(
    repository: TrainingIncrementalRepository, database_path: Path,
    verification_case_public_id: str,
) -> None:
    run = _build_run(repository, database_path, verification_case_public_id)
    checkpoint = repository.add_checkpoint(
        run["public_id"], {"underlying_checkpoint_public_id": "ckpt-3"}
    )
    report = repository.add_report(
        run["public_id"],
        {
            "report": {"summary": "v1"}, "report_checksum_sha256": "chk-1",
            "checkpoint_recommendation": "accept_candidate",
            "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    acceptance = repository.add_acceptance(
        checkpoint["public_id"],
        {
            "report_public_id": report["public_id"], "decision": "accepted_candidate",
            "reason": "metrics acceptable", "reviewer_admin_public_id": ADMIN_ID,
            "report_checksum_sha256": report["report_checksum_sha256"],
            "target_fingerprint": "fp-accept-1",
        },
    )
    assert acceptance["decision"] == "accepted_candidate"
    assert repository.get_latest_acceptance(checkpoint["public_id"])["public_id"] == (
        acceptance["public_id"]
    )
    assert len(repository.list_acceptances(checkpoint["public_id"])) == 1
