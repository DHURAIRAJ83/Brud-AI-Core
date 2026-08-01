from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.governance import GovernanceRepository, public_row


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "governance.db"
    initialize_database(path)
    return path


@pytest.fixture
def repository(database_path: Path) -> GovernanceRepository:
    return GovernanceRepository(database_path)


def test_next_review_code_is_sequential(repository: GovernanceRepository) -> None:
    with repository.transaction() as connection:
        assert repository.next_review_code(connection) == "REV-0001"
        repository.create_review_item(
            connection,
            {
                "review_code": "REV-0001",
                "entity_type": "document_page",
                "entity_public_id": "page-1",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        assert repository.next_review_code(connection) == "REV-0002"


def test_create_and_find_open_review_item(repository: GovernanceRepository) -> None:
    with repository.transaction() as connection:
        public_id = repository.create_review_item(
            connection,
            {
                "review_code": "REV-0100",
                "entity_type": "manual_data_record",
                "entity_public_id": "mdr-1",
                "priority": "high",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        row = public_row(repository.review_item(connection, public_id))
        assert row["status"] == "open"
        assert row["priority"] == "high"
        assert "id" not in row
        found = repository.find_open_review_item(connection, "manual_data_record", "mdr-1")
        assert found is not None
        assert found["public_id"] == public_id


def test_find_open_review_item_ignores_resolved_items(repository: GovernanceRepository) -> None:
    with repository.transaction() as connection:
        public_id = repository.create_review_item(
            connection,
            {
                "review_code": "REV-0200",
                "entity_type": "semantic_chunk",
                "entity_public_id": "chunk-9",
                "created_by_admin_public_id": "admin-1",
            },
        )
        item_id = repository.review_item(connection, public_id)["id"]
        repository.update_review_item(connection, item_id, {"status": "resolved"})
    with repository.transaction() as connection:
        assert repository.find_open_review_item(connection, "semantic_chunk", "chunk-9") is None


def test_unique_constraint_prevents_two_open_items_for_same_entity(
    repository: GovernanceRepository,
) -> None:
    from backend.database.repositories.base import ConflictError

    with repository.transaction() as connection:
        repository.create_review_item(
            connection,
            {
                "review_code": "REV-0300",
                "entity_type": "dataset_record",
                "entity_public_id": "rec-1",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with pytest.raises(ConflictError):
        with repository.transaction() as connection:
            repository.create_review_item(
                connection,
                {
                    "review_code": "REV-0301",
                    "entity_type": "dataset_record",
                    "entity_public_id": "rec-1",
                    "created_by_admin_public_id": "admin-1",
                },
            )


def test_list_review_items_orders_by_priority(repository: GovernanceRepository) -> None:
    with repository.transaction() as connection:
        for code, entity, priority in (
            ("REV-0400", "doc-a", "low"),
            ("REV-0401", "doc-b", "urgent"),
            ("REV-0402", "doc-c", "normal"),
        ):
            repository.create_review_item(
                connection,
                {
                    "review_code": code,
                    "entity_type": "document_page",
                    "entity_public_id": entity,
                    "priority": priority,
                    "created_by_admin_public_id": "admin-1",
                },
            )
    with repository.transaction() as connection:
        rows, total = repository.list_review_items(connection)
        assert total >= 3
        priorities = [row["priority"] for row in rows if row["entity_public_id"].startswith("doc-")]
        assert priorities[0] == "urgent"


def test_issues_created_and_resolved(repository: GovernanceRepository) -> None:
    with repository.transaction() as connection:
        item_public_id = repository.create_review_item(
            connection,
            {
                "review_code": "REV-0500",
                "entity_type": "document_page",
                "entity_public_id": "page-5",
                "created_by_admin_public_id": "admin-1",
            },
        )
        item_id = repository.review_item(connection, item_public_id)["id"]
        issue_public_id = repository.create_issue(
            connection,
            {
                "review_item_id": item_id,
                "issue_code": "X1",
                "issue_category": "language_quality",
                "severity": "warning",
                "is_blocking": False,
                "message": "msg",
                "detector": "test",
            },
        )
    with repository.transaction() as connection:
        item_id = repository.review_item(connection, item_public_id)["id"]
        issues = repository.issues_for_item(connection, item_id)
        assert len(issues) == 1
        assert issues[0]["resolved_at"] is None
        repository.resolve_issue(connection, issue_public_id)
    with repository.transaction() as connection:
        item_id = repository.review_item(connection, item_public_id)["id"]
        open_issues = repository.issues_for_item(connection, item_id, open_only=True)
        assert open_issues == []


def test_duplicate_group_lifecycle(repository: GovernanceRepository) -> None:
    with repository.transaction() as connection:
        assert repository.next_group_code(connection, "duplicate") == "DUP-0001"
        group_public_id = repository.create_duplicate_group(
            connection,
            {
                "group_code": "DUP-0001",
                "duplicate_type": "exact",
                "match_reason": "identical content hash",
            },
        )
        group_id = repository.duplicate_group(connection, group_public_id)["id"]
        repository.add_duplicate_member(connection, group_id, "manual_data_record", "mdr-a")
        repository.add_duplicate_member(
            connection, group_id, "manual_data_record", "mdr-b", role="canonical"
        )
    with repository.transaction() as connection:
        group_id = repository.duplicate_group(connection, group_public_id)["id"]
        members = repository.duplicate_group_members(connection, group_id)
        assert len(members) == 2
        found = repository.find_open_duplicate_group_for_entity(
            connection, "manual_data_record", "mdr-a"
        )
        assert found is not None
        assert found["public_id"] == group_public_id
        repository.resolve_duplicate_group(connection, group_id)
    with repository.transaction() as connection:
        assert (
            repository.find_open_duplicate_group_for_entity(
                connection, "manual_data_record", "mdr-a"
            )
            is None
        )


def test_conflict_group_lifecycle(repository: GovernanceRepository) -> None:
    with repository.transaction() as connection:
        group_public_id = repository.create_conflict_group(
            connection,
            {
                "group_code": "CFL-0001",
                "conflict_type": "dictionary_sense",
                "match_reason": "same word, different meanings",
            },
        )
        group_id = repository.conflict_group(connection, group_public_id)["id"]
        repository.add_conflict_member(connection, group_id, "manual_data_record", "mdr-x")
    with repository.transaction() as connection:
        group_id = repository.conflict_group(connection, group_public_id)["id"]
        members = repository.conflict_group_members(connection, group_id)
        assert len(members) == 1
        found = repository.find_open_conflict_group_for_entity(
            connection, "manual_data_record", "mdr-x"
        )
        assert found is not None


def test_resolution_requires_a_group_and_is_linked(repository: GovernanceRepository) -> None:
    with repository.transaction() as connection:
        group_public_id = repository.create_duplicate_group(
            connection,
            {
                "group_code": "DUP-0050",
                "duplicate_type": "normalized",
                "match_reason": "same normalized text",
            },
        )
        group_id = repository.duplicate_group(connection, group_public_id)["id"]
        repository.create_resolution(
            connection,
            {
                "duplicate_group_id": group_id,
                "resolution_action": "not_a_duplicate",
                "resolution_reason": "different context",
                "performed_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        group_id = repository.duplicate_group(connection, group_public_id)["id"]
        resolutions = repository.resolutions_for_duplicate_group(connection, group_id)
        assert len(resolutions) == 1
        assert resolutions[0]["resolution_action"] == "not_a_duplicate"


def test_target_approval_new_row_per_decision_and_latest_lookup(
    repository: GovernanceRepository,
) -> None:
    with repository.transaction() as connection:
        item_public_id = repository.create_review_item(
            connection,
            {
                "review_code": "REV-0600",
                "entity_type": "document_page",
                "entity_public_id": "page-6",
                "created_by_admin_public_id": "admin-1",
            },
        )
        item_id = repository.review_item(connection, item_public_id)["id"]
        repository.create_target_approval(
            connection,
            {
                "review_item_id": item_id,
                "entity_type": "document_page",
                "entity_public_id": "page-6",
                "target_use": "rag",
                "decision": "blocked",
                "decision_code": "BLOCKED_RIGHTS_UNKNOWN",
                "decided_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        latest = repository.latest_target_approval(connection, "document_page", "page-6", "rag")
        assert latest["decision"] == "blocked"
        item_id = repository.review_item(connection, item_public_id)["id"]
        repository.create_target_approval(
            connection,
            {
                "review_item_id": item_id,
                "entity_type": "document_page",
                "entity_public_id": "page-6",
                "target_use": "rag",
                "decision": "allowed",
                "decision_code": "ALLOWED",
                "decided_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        latest = repository.latest_target_approval(connection, "document_page", "page-6", "rag")
        assert latest["decision"] == "allowed"
        history = repository.target_approval_history(
            connection, "document_page", "page-6", "rag"
        )
        assert len(history) == 2


def test_events_are_recorded_and_listed(repository: GovernanceRepository) -> None:
    with repository.transaction() as connection:
        item_public_id = repository.create_review_item(
            connection,
            {
                "review_code": "REV-0700",
                "entity_type": "document_page",
                "entity_public_id": "page-7",
                "created_by_admin_public_id": "admin-1",
            },
        )
        item_id = repository.review_item(connection, item_public_id)["id"]
        repository.create_event(
            connection,
            {
                "review_item_id": item_id,
                "event_type": "review_item_created",
                "performed_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        item_id = repository.review_item(connection, item_public_id)["id"]
        events = repository.events_for_item(connection, item_id)
        assert len(events) == 1
        assert events[0]["event_type"] == "review_item_created"


def test_review_queue_counts(repository: GovernanceRepository) -> None:
    with repository.transaction() as connection:
        repository.create_review_item(
            connection,
            {
                "review_code": "REV-0800",
                "entity_type": "document_page",
                "entity_public_id": "page-8",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        counts = repository.review_queue_counts(connection)
        assert counts.get("open", 0) >= 1
