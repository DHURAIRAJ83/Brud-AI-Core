from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.governed_builds import GovernedBuildRepository, public_row


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "governed_builds.db"
    initialize_database(path)
    return path


@pytest.fixture
def repository(database_path: Path) -> GovernedBuildRepository:
    return GovernedBuildRepository(database_path)


def test_next_build_code_is_sequential(repository: GovernedBuildRepository) -> None:
    with repository.transaction() as connection:
        assert repository.next_build_code(connection) == "GBR-0001"
        repository.create_build_request(
            connection,
            {
                "build_code": "GBR-0001",
                "target_pipeline": "rag",
                "requested_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        assert repository.next_build_code(connection) == "GBR-0002"


def test_create_and_read_build_request(repository: GovernedBuildRepository) -> None:
    with repository.transaction() as connection:
        public_id = repository.create_build_request(
            connection,
            {
                "build_code": "GBR-0100",
                "target_pipeline": "pretraining",
                "build_label": "Q1 pretraining slice",
                "requested_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        row = public_row(repository.build_request(connection, public_id))
        assert row["status"] == "draft"
        assert row["build_label"] == "Q1 pretraining slice"
        assert "id" not in row
        repository.update_build_request(
            connection, repository.build_request(connection, public_id)["id"],
            {"status": "preflight_ready"},
        )
    with repository.transaction() as connection:
        row = public_row(repository.build_request(connection, public_id))
        assert row["status"] == "preflight_ready"


def test_list_build_requests_filters_and_counts(repository: GovernedBuildRepository) -> None:
    with repository.transaction() as connection:
        for code, target in (("GBR-0200", "rag"), ("GBR-0201", "evaluation")):
            repository.create_build_request(
                connection,
                {
                    "build_code": code,
                    "target_pipeline": target,
                    "requested_by_admin_public_id": "admin-1",
                },
            )
    with repository.transaction() as connection:
        rows, total = repository.list_build_requests(connection, target_pipeline="rag")
        assert total >= 1
        assert all(row["target_pipeline"] == "rag" for row in rows)
        counts = repository.counts_by_status(connection)
        assert counts.get("draft", 0) >= 2


def test_preflight_result_and_items_lifecycle(repository: GovernedBuildRepository) -> None:
    with repository.transaction() as connection:
        request_id_public = repository.create_build_request(
            connection,
            {
                "build_code": "GBR-0300",
                "target_pipeline": "dataset_version",
                "requested_by_admin_public_id": "admin-1",
            },
        )
        request_id = repository.build_request(connection, request_id_public)["id"]
        preflight_public_id = repository.create_preflight_result(
            connection,
            {
                "build_request_id": request_id,
                "target_pipeline": "dataset_version",
                "eligible_count": 1,
                "created_by_admin_public_id": "admin-1",
            },
        )
        preflight_id = repository.preflight_result(connection, preflight_public_id)["id"]
        item_public_id = repository.create_request_item(
            connection,
            {
                "build_request_id": request_id,
                "preflight_result_id": preflight_id,
                "entity_type": "dataset_record",
                "entity_public_id": "rec-1",
                "decision": "eligible",
                "decision_code": "ELIGIBLE",
                "included": True,
            },
        )
    with repository.transaction() as connection:
        request_id = repository.build_request(connection, request_id_public)["id"]
        latest = repository.latest_preflight_result(connection, request_id)
        assert latest["public_id"] == preflight_public_id
        items = repository.items_for_build_request(connection, request_id)
        assert len(items) == 1
        assert items[0]["public_id"] == item_public_id
        item = repository.request_item(connection, item_public_id)
        repository.update_request_item(connection, item["id"], {"included": 0})
    with repository.transaction() as connection:
        request_id = repository.build_request(connection, request_id_public)["id"]
        included = repository.items_for_build_request(connection, request_id, included_only=True)
        assert included == []


def test_preflight_results_history_keeps_every_run(repository: GovernedBuildRepository) -> None:
    with repository.transaction() as connection:
        request_public_id = repository.create_build_request(
            connection,
            {
                "build_code": "GBR-0400",
                "target_pipeline": "rag",
                "requested_by_admin_public_id": "admin-1",
            },
        )
        request_id = repository.build_request(connection, request_public_id)["id"]
        repository.create_preflight_result(
            connection,
            {
                "build_request_id": request_id,
                "target_pipeline": "rag",
                "created_by_admin_public_id": "admin-1",
            },
        )
        repository.create_preflight_result(
            connection,
            {
                "build_request_id": request_id,
                "target_pipeline": "rag",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        request_id = repository.build_request(connection, request_public_id)["id"]
        history = repository.list_preflight_results(connection, request_id)
        assert len(history) == 2


def test_previously_included_entity_ids_only_counts_completed_builds(
    repository: GovernedBuildRepository,
) -> None:
    with repository.transaction() as connection:
        request_public_id = repository.create_build_request(
            connection,
            {
                "build_code": "GBR-0500",
                "target_pipeline": "rag",
                "requested_by_admin_public_id": "admin-1",
            },
        )
        request_id = repository.build_request(connection, request_public_id)["id"]
        preflight_id = repository.preflight_result(
            connection,
            repository.create_preflight_result(
                connection,
                {
                    "build_request_id": request_id,
                    "target_pipeline": "rag",
                    "created_by_admin_public_id": "admin-1",
                },
            ),
        )["id"]
        repository.create_request_item(
            connection,
            {
                "build_request_id": request_id,
                "preflight_result_id": preflight_id,
                "entity_type": "dataset_record",
                "entity_public_id": "rec-dup",
                "decision": "eligible",
                "decision_code": "ELIGIBLE",
                "included": True,
            },
        )
    with repository.transaction() as connection:
        request_id = repository.build_request(connection, request_public_id)["id"]
        # Not completed yet -- must not count as a prior export.
        seen = repository.previously_included_entity_ids(
            connection, target_pipeline="rag", entity_type="dataset_record",
            entity_public_ids=["rec-dup"],
        )
        assert seen == set()
        repository.update_build_request(connection, request_id, {"status": "completed"})
    with repository.transaction() as connection:
        seen = repository.previously_included_entity_ids(
            connection, target_pipeline="rag", entity_type="dataset_record",
            entity_public_ids=["rec-dup"],
        )
        assert seen == {"rec-dup"}


def test_prior_evaluation_entity_ids_only_from_completed_evaluation_builds(
    repository: GovernedBuildRepository,
) -> None:
    with repository.transaction() as connection:
        request_public_id = repository.create_build_request(
            connection,
            {
                "build_code": "GBR-0600",
                "target_pipeline": "evaluation",
                "requested_by_admin_public_id": "admin-1",
            },
        )
        request_id = repository.build_request(connection, request_public_id)["id"]
        preflight_id = repository.preflight_result(
            connection,
            repository.create_preflight_result(
                connection,
                {
                    "build_request_id": request_id,
                    "target_pipeline": "evaluation",
                    "created_by_admin_public_id": "admin-1",
                },
            ),
        )["id"]
        repository.create_request_item(
            connection,
            {
                "build_request_id": request_id,
                "preflight_result_id": preflight_id,
                "entity_type": "dataset_record",
                "entity_public_id": "rec-eval",
                "decision": "eligible",
                "decision_code": "ELIGIBLE",
                "included": True,
            },
        )
    with repository.transaction() as connection:
        assert repository.prior_evaluation_entity_ids(connection) == frozenset()
        request_id = repository.build_request(connection, request_public_id)["id"]
        repository.update_build_request(connection, request_id, {"status": "completed"})
    with repository.transaction() as connection:
        assert repository.prior_evaluation_entity_ids(connection) == frozenset({"rec-eval"})


def test_artifact_link_created_and_looked_up_by_artifact(
    repository: GovernedBuildRepository,
) -> None:
    with repository.transaction() as connection:
        request_public_id = repository.create_build_request(
            connection,
            {
                "build_code": "GBR-0700",
                "target_pipeline": "dataset_version",
                "requested_by_admin_public_id": "admin-1",
            },
        )
        request_id = repository.build_request(connection, request_public_id)["id"]
        repository.create_artifact_link(
            connection,
            {
                "build_request_id": request_id,
                "artifact_type": "dataset_version",
                "artifact_public_id": "ver-1",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        request_id = repository.build_request(connection, request_public_id)["id"]
        links = repository.artifact_links_for_request(connection, request_id)
        assert len(links) == 1
        found = repository.find_links_by_artifact(connection, "dataset_version", "ver-1")
        assert len(found) == 1


def test_lineage_edge_create_is_idempotent(repository: GovernedBuildRepository) -> None:
    with repository.transaction() as connection:
        first = repository.create_lineage_edge(
            connection,
            {
                "upstream_entity_type": "manual_data_record",
                "upstream_entity_id": "rec-1",
                "downstream_entity_type": "dataset_record",
                "downstream_entity_id": "ds-1",
                "relationship_type": "derived_from",
                "created_by_admin_public_id": "admin-1",
            },
        )
        second = repository.create_lineage_edge(
            connection,
            {
                "upstream_entity_type": "manual_data_record",
                "upstream_entity_id": "rec-1",
                "downstream_entity_type": "dataset_record",
                "downstream_entity_id": "ds-1",
                "relationship_type": "derived_from",
                "created_by_admin_public_id": "admin-1",
            },
        )
        assert first == second
    with repository.transaction() as connection:
        upstream = repository.edges_upstream_of(connection, "dataset_record", "ds-1")
        assert len(upstream) == 1
        downstream = repository.edges_downstream_of(connection, "manual_data_record", "rec-1")
        assert len(downstream) == 1


def test_lineage_events_recorded_and_listed(repository: GovernedBuildRepository) -> None:
    with repository.transaction() as connection:
        request_public_id = repository.create_build_request(
            connection,
            {
                "build_code": "GBR-0800",
                "target_pipeline": "rag",
                "requested_by_admin_public_id": "admin-1",
            },
        )
        request_id = repository.build_request(connection, request_public_id)["id"]
        repository.create_lineage_event(
            connection,
            {
                "build_request_id": request_id,
                "event_type": "build_request_created",
                "performed_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        request_id = repository.build_request(connection, request_public_id)["id"]
        events = repository.lineage_events_for_request(connection, request_id)
        assert len(events) == 1
        assert events[0]["event_type"] == "build_request_created"
