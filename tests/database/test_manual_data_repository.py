from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.base import ConflictError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.manual_data import ManualDataRepository, public_row


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "manual_data.db"
    initialize_database(path)
    return path


@pytest.fixture
def repository(database_path: Path) -> ManualDataRepository:
    return ManualDataRepository(database_path)


def _make_source(database_path: Path) -> int:
    source_repo = DataSourceRepository(database_path)
    with source_repo.transaction() as connection:
        public_id = source_repo.create_source(
            connection,
            {
                "source_code": "SRC-MD-TEST-0001",
                "title": "Dhurai -- Spoken Tamil",
                "source_type": "human_created",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with source_repo.transaction() as connection:
        return source_repo.source(connection, public_id)["id"]


def test_create_read_update_record(
    repository: ManualDataRepository, database_path: Path
) -> None:
    source_id = _make_source(database_path)
    with repository.transaction() as connection:
        public_id = repository.create_record(
            connection,
            {
                "record_code": "MD-0001",
                "record_type": "plain_text",
                "source_id": source_id,
                "primary_language": "ta",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        row = public_row(repository.record(connection, public_id))
        assert row["record_code"] == "MD-0001"
        assert row["status"] == "draft"
        assert row["requested_uses"] == []
        assert "id" not in row
        assert "source_id" not in row

        repository.update_record(
            connection, repository.record(connection, public_id)["id"], {"status": "needs_review"}
        )
    with repository.transaction() as connection:
        row = public_row(repository.record(connection, public_id))
        assert row["status"] == "needs_review"


def test_record_code_is_unique(repository: ManualDataRepository, database_path: Path) -> None:
    source_id = _make_source(database_path)
    with repository.transaction() as connection:
        repository.create_record(
            connection,
            {
                "record_code": "MD-DUP-0001",
                "record_type": "plain_text",
                "source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )
    with pytest.raises(ConflictError), repository.transaction() as connection:
        repository.create_record(
            connection,
            {
                "record_code": "MD-DUP-0001",
                "record_type": "plain_text",
                "source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )


def test_list_records_filters_and_paginates(
    repository: ManualDataRepository, database_path: Path
) -> None:
    source_id = _make_source(database_path)
    with repository.transaction() as connection:
        for i in range(3):
            repository.create_record(
                connection,
                {
                    "record_code": f"MD-LIST-{i:04d}",
                    "record_type": "dictionary_entry",
                    "source_id": source_id,
                    "created_by_admin_public_id": "admin-1",
                },
            )
        repository.create_record(
            connection,
            {
                "record_code": "MD-LIST-CONVO",
                "record_type": "conversation",
                "source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        rows, total = repository.list_records(connection, record_type="dictionary_entry")
        assert total == 3
        assert len(rows) == 3

        rows, total = repository.list_records(connection, search="CONVO")
        assert total == 1

        rows, total = repository.list_records(connection, limit=2, offset=0)
        assert total == 4
        assert len(rows) == 2


def test_summary_and_group_counts(repository: ManualDataRepository, database_path: Path) -> None:
    source_id = _make_source(database_path)
    with repository.transaction() as connection:
        repository.create_record(
            connection,
            {
                "record_code": "MD-SUM-0001",
                "record_type": "plain_text",
                "source_id": source_id,
                "primary_language": "ta",
                "created_by_admin_public_id": "admin-1",
            },
        )
        repository.create_record(
            connection,
            {
                "record_code": "MD-SUM-0002",
                "record_type": "dictionary_entry",
                "source_id": source_id,
                "primary_language": "en",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        counts = repository.summary_counts(connection)
        assert counts["draft"] == 2
        by_type = repository.counts_by(connection, "record_type")
        assert by_type["plain_text"] == 1
        assert by_type["dictionary_entry"] == 1


def test_revision_lifecycle_and_content_hash_lookup(
    repository: ManualDataRepository, database_path: Path
) -> None:
    source_id = _make_source(database_path)
    with repository.transaction() as connection:
        public_id = repository.create_record(
            connection,
            {
                "record_code": "MD-REV-0001",
                "record_type": "plain_text",
                "source_id": source_id,
                "primary_language": "ta",
                "created_by_admin_public_id": "admin-1",
            },
        )
        record_id = repository.record(connection, public_id)["id"]
        assert repository.latest_revision_number(connection, record_id) == 0
        revision_public_id = repository.create_revision(
            connection,
            {
                "record_id": record_id,
                "revision_number": 1,
                "tamil_text": "வணக்கம்",
                "content_hash": "hash-1",
                "created_by_admin_public_id": "admin-1",
            },
        )
        revision_id = repository.revision(connection, revision_public_id)["id"]
        repository.update_record(connection, record_id, {"active_revision_id": revision_id})
    with repository.transaction() as connection:
        assert repository.latest_revision_number(connection, record_id) == 1
        revisions = [public_row(r) for r in repository.list_revisions(connection, record_id)]
        assert len(revisions) == 1
        assert revisions[0]["tamil_text"] == "வணக்கம்"

        found = repository.content_hash_exists(connection, "hash-1")
        assert found is not None
        not_found = repository.content_hash_exists(connection, "hash-does-not-exist")
        assert not_found is None
        excluded = repository.content_hash_exists(
            connection, "hash-1", exclude_record_id=record_id
        )
        assert excluded is None


def test_dictionary_word_duplicate_lookup(
    repository: ManualDataRepository, database_path: Path
) -> None:
    source_id = _make_source(database_path)
    with repository.transaction() as connection:
        public_id = repository.create_record(
            connection,
            {
                "record_code": "MD-DICT-0001",
                "record_type": "dictionary_entry",
                "source_id": source_id,
                "primary_language": "ta",
                "created_by_admin_public_id": "admin-1",
            },
        )
        record_id = repository.record(connection, public_id)["id"]
        revision_public_id = repository.create_revision(
            connection,
            {
                "record_id": record_id,
                "revision_number": 1,
                "word": "நல்லது",
                "meanings_json": '["good"]',
                "content_hash": "hash-dict-1",
                "created_by_admin_public_id": "admin-1",
            },
        )
        revision_id = repository.revision(connection, revision_public_id)["id"]
        repository.update_record(connection, record_id, {"active_revision_id": revision_id})
    with repository.transaction() as connection:
        found = repository.dictionary_word_exists(connection, "ta:நல்லது")
        assert found is not None
        not_found = repository.dictionary_word_exists(connection, "en:நல்லது")
        assert not_found is None


def test_review_verification_usage_decision_and_event_history(
    repository: ManualDataRepository, database_path: Path
) -> None:
    source_id = _make_source(database_path)
    with repository.transaction() as connection:
        public_id = repository.create_record(
            connection,
            {
                "record_code": "MD-FULL-0001",
                "record_type": "knowledge_note",
                "source_id": source_id,
                "knowledge_risk": "high_risk",
                "fact_dependency": "high",
                "created_by_admin_public_id": "admin-1",
            },
        )
        record_id = repository.record(connection, public_id)["id"]
        revision_public_id = repository.create_revision(
            connection,
            {
                "record_id": record_id,
                "revision_number": 1,
                "title": "Procedure",
                "content_hash": "hash-full-1",
                "created_by_admin_public_id": "admin-1",
            },
        )
        revision_id = repository.revision(connection, revision_public_id)["id"]

        repository.create_review(
            connection,
            {
                "record_id": record_id,
                "revision_id": revision_id,
                "review_type": "domain",
                "review_status": "changes_requested",
                "reviewer_admin_public_id": "admin-2",
                "comments": "Needs a supporting source.",
            },
        )
        repository.create_verification(
            connection,
            {
                "record_id": record_id,
                "revision_id": revision_id,
                "verification_type": "factual_verification",
                "verification_status": "pending",
                "source_id": source_id,
            },
        )
        repository.add_usage_decision(
            connection,
            {
                "record_id": record_id,
                "revision_id": revision_id,
                "target_use": "training",
                "allowed": False,
                "decision_code": "BLOCKED_HIGH_RISK_UNVERIFIED",
            },
        )
        repository.add_event(
            connection,
            {
                "record_id": record_id,
                "event_type": "record_created",
                "status_after": "draft",
                "performed_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        reviews = [public_row(r) for r in repository.list_reviews(connection, record_id)]
        assert len(reviews) == 1
        assert reviews[0]["review_status"] == "changes_requested"

        verifications = [
            public_row(v) for v in repository.list_verifications(connection, record_id)
        ]
        assert len(verifications) == 1
        assert verifications[0]["verification_status"] == "pending"

        decisions = [
            public_row(d) for d in repository.list_usage_decisions(connection, record_id)
        ]
        assert len(decisions) == 1
        assert decisions[0]["decision_code"] == "BLOCKED_HIGH_RISK_UNVERIFIED"

        events = [public_row(e) for e in repository.list_events(connection, record_id)]
        assert len(events) == 1
        assert events[0]["event_type"] == "record_created"
