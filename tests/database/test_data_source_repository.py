from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.base import ConflictError
from backend.database.repositories.data_sources import DataSourceRepository, public_row


@pytest.fixture
def repository(tmp_path: Path) -> DataSourceRepository:
    database_path = tmp_path / "data_sources.db"
    initialize_database(database_path)
    return DataSourceRepository(database_path)


def test_create_read_update_source(repository: DataSourceRepository) -> None:
    with repository.transaction() as connection:
        public_id = repository.create_source(
            connection,
            {
                "source_code": "SRC-HUMAN-TEST-0001",
                "title": "Spoken Tamil examples",
                "source_type": "human_created",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        row = public_row(repository.source(connection, public_id))
        assert row["source_code"] == "SRC-HUMAN-TEST-0001"
        assert row["status"] == "draft"
        assert row["language_codes"] == []
        assert "id" not in row

        repository.update_source(
            connection, repository.source(connection, public_id)["id"], {"status": "needs_review"}
        )

    with repository.transaction() as connection:
        row = public_row(repository.source(connection, public_id))
        assert row["status"] == "needs_review"


def test_source_code_is_unique(repository: DataSourceRepository) -> None:
    with repository.transaction() as connection:
        repository.create_source(
            connection,
            {
                "source_code": "SRC-DUP-0001",
                "title": "First",
                "source_type": "human_created",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with pytest.raises(ConflictError), repository.transaction() as connection:
        repository.create_source(
            connection,
            {
                "source_code": "SRC-DUP-0001",
                "title": "Second",
                "source_type": "human_created",
                "created_by_admin_public_id": "admin-1",
            },
        )


def test_list_sources_filters_and_paginates(repository: DataSourceRepository) -> None:
    with repository.transaction() as connection:
        for i in range(3):
            repository.create_source(
                connection,
                {
                    "source_code": f"SRC-LIST-{i:04d}",
                    "title": f"Government PDF {i}",
                    "source_type": "government_source",
                    "created_by_admin_public_id": "admin-1",
                },
            )
        repository.create_source(
            connection,
            {
                "source_code": "SRC-LIST-HUMAN",
                "title": "Spoken phrase",
                "source_type": "human_created",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        rows, total = repository.list_sources(connection, source_type="government_source")
        assert total == 3
        assert len(rows) == 3

        rows, total = repository.list_sources(connection, search="Spoken")
        assert total == 1
        assert public_row(rows[0])["source_code"] == "SRC-LIST-HUMAN"

        rows, total = repository.list_sources(connection, limit=2, offset=0)
        assert total == 4
        assert len(rows) == 2


def test_rights_lifecycle_and_verification_events(repository: DataSourceRepository) -> None:
    with repository.transaction() as connection:
        source_id_public = repository.create_source(
            connection,
            {
                "source_code": "SRC-RIGHTS-0001",
                "title": "Test",
                "source_type": "document_derived",
                "created_by_admin_public_id": "admin-1",
            },
        )
        source_id = repository.source(connection, source_id_public)["id"]
        assert repository.rights_for_source(connection, source_id) is None

        repository.create_rights(
            connection,
            source_id,
            {"rights_status": "pending_review", "verification_status": "unverified"},
        )

    with repository.transaction() as connection:
        rights = public_row(repository.rights_for_source(connection, source_id))
        assert rights["rights_status"] == "pending_review"

        repository.add_verification_event(
            connection,
            {
                "data_source_id": source_id,
                "action": "document_verify",
                "verification_status_after": "document_verified",
                "performed_by_admin_public_id": "admin-2",
                "notes": "Checked the licence PDF.",
            },
        )

    with repository.transaction() as connection:
        events = [
            public_row(row) for row in repository.list_verification_events(connection, source_id)
        ]
        assert len(events) == 1
        assert events[0]["action"] == "document_verify"


def test_usage_decisions_are_recorded_and_latest_wins(repository: DataSourceRepository) -> None:
    with repository.transaction() as connection:
        public_id = repository.create_source(
            connection,
            {
                "source_code": "SRC-USAGE-0001",
                "title": "Test",
                "source_type": "human_created",
                "created_by_admin_public_id": "admin-1",
            },
        )
        source_id = repository.source(connection, public_id)["id"]
        repository.add_usage_decision(
            connection,
            {
                "data_source_id": source_id,
                "target_use": "training",
                "allowed": False,
                "decision_code": "BLOCKED_RIGHTS_UNKNOWN",
            },
        )
        repository.add_usage_decision(
            connection,
            {
                "data_source_id": source_id,
                "target_use": "training",
                "allowed": True,
                "decision_code": "ALLOWED",
            },
        )
    with repository.transaction() as connection:
        latest = public_row(repository.latest_usage_decision(connection, source_id, "training"))
        assert latest["decision_code"] == "ALLOWED"
        history = repository.list_usage_decisions(connection, source_id)
        assert len(history) == 2


def test_link_create_list_and_delete(repository: DataSourceRepository) -> None:
    with repository.transaction() as connection:
        public_id = repository.create_source(
            connection,
            {
                "source_code": "SRC-LINK-0001",
                "title": "Test",
                "source_type": "human_created",
                "created_by_admin_public_id": "admin-1",
            },
        )
        source_id = repository.source(connection, public_id)["id"]
        link_public_id = repository.create_link(
            connection,
            {
                "data_source_id": source_id,
                "entity_type": "dataset_record",
                "entity_public_id": "record-abc",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        links = [public_row(row) for row in repository.list_links(connection, source_id)]
        assert len(links) == 1
        assert links[0]["entity_public_id"] == "record-abc"
        assert repository.link_count(connection, source_id) == 1

        by_entity = repository.links_for_entity(connection, "dataset_record", "record-abc")
        assert len(by_entity) == 1

        link_row = repository.link(connection, link_public_id)
        repository.delete_link(connection, link_row["id"])
    with repository.transaction() as connection:
        assert repository.link_count(connection, source_id) == 0
