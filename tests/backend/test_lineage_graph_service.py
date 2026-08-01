from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.lineage_graph_service import LineageGraphService

ADMIN = "admin-1"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "lineage.db"
    initialize_database(database_path)
    return Settings(
        database_path=database_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )


@pytest.fixture
def lineage(settings: Settings) -> LineageGraphService:
    return LineageGraphService(settings)


class TestLineageEdges:
    def test_create_edge_and_query_upstream_downstream(self, lineage: LineageGraphService):
        lineage.create_edge(
            upstream_entity_type="manual_data_record",
            upstream_entity_id="mdr-1",
            downstream_entity_type="dataset_record",
            downstream_entity_id="ds-1",
            relationship_type="derived_from",
            admin_id=ADMIN,
        )
        upstream = lineage.upstream_of("dataset_record", "ds-1")
        assert len(upstream["items"]) == 1
        assert upstream["items"][0]["upstream_entity_id"] == "mdr-1"

        downstream = lineage.downstream_of("manual_data_record", "mdr-1")
        assert len(downstream["items"]) == 1
        assert downstream["items"][0]["downstream_entity_id"] == "ds-1"

    def test_create_edge_is_idempotent(self, lineage: LineageGraphService):
        first = lineage.create_edge(
            upstream_entity_type="semantic_chunk",
            upstream_entity_id="chunk-1",
            downstream_entity_type="dataset_record",
            downstream_entity_id="ds-2",
            relationship_type="included_in",
            admin_id=ADMIN,
        )
        second = lineage.create_edge(
            upstream_entity_type="semantic_chunk",
            upstream_entity_id="chunk-1",
            downstream_entity_type="dataset_record",
            downstream_entity_id="ds-2",
            relationship_type="included_in",
            admin_id=ADMIN,
        )
        assert first["public_id"] == second["public_id"]


class TestTrace:
    def test_trace_follows_a_multi_hop_chain_in_both_directions(
        self, lineage: LineageGraphService
    ):
        lineage.create_edge(
            upstream_entity_type="manual_data_record",
            upstream_entity_id="mdr-a",
            downstream_entity_type="dataset_record",
            downstream_entity_id="ds-a",
            relationship_type="derived_from",
            admin_id=ADMIN,
        )
        lineage.create_edge(
            upstream_entity_type="dataset_record",
            upstream_entity_id="ds-a",
            downstream_entity_type="dataset_version",
            downstream_entity_id="ver-a",
            relationship_type="included_in",
            admin_id=ADMIN,
        )
        trace = lineage.trace("dataset_record", "ds-a")
        assert trace["complete"] is True
        node_ids = {n["entity_id"] for n in trace["nodes"]}
        assert node_ids == {"mdr-a", "ds-a", "ver-a"}
        assert len(trace["edges"]) == 2

    def test_trace_of_an_isolated_entity_is_marked_incomplete(
        self, lineage: LineageGraphService
    ):
        trace = lineage.trace("dataset_record", "no-lineage-at-all")
        assert trace["complete"] is False
        assert trace["edges"] == []


class TestModelReleaseLineage:
    def test_for_model_release_with_no_matching_release_is_incomplete(
        self, lineage: LineageGraphService
    ):
        result = lineage.for_model_release("does-not-exist")
        assert result["complete"] is False
        assert result["direct_lineage"] == {}
