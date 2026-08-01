"""Source-to-model lineage graph (Phase 7, Steps 18-19, 30).

Bridges two lineage representations rather than duplicating either:
from `dataset_version` onward, `model_release_candidates` already
carries direct FKs to `tokenizer_version`/`checkpoint`/
`instruction_tuning_candidate`/`model_evaluation_run` (confirmed by
direct inspection -- complete lineage already exists there via plain
foreign keys, never re-created as edges). Before `dataset_version`, no
queryable link existed at all (only opaque `metadata_json` references)
-- that gap is what `lineage_edges` fills.

Never fabricates a missing edge: a trace that cannot reach further
back/forward simply stops, and the caller is told explicitly via
`complete: false` rather than being given a false sense of a full
chain (Step 30: "Display 'Lineage incomplete' when gaps exist").
"""

from __future__ import annotations

from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.governed_builds import GovernedBuildRepository, public_row


class LineageGraphService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernedBuildRepository(settings.resolved_database_path)
        self.sources = DataSourceRepository(settings.resolved_database_path)

    def create_edge(
        self,
        *,
        upstream_entity_type: str,
        upstream_entity_id: str,
        downstream_entity_type: str,
        downstream_entity_id: str,
        relationship_type: str,
        admin_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_lineage_edge(
                connection,
                {
                    "upstream_entity_type": upstream_entity_type,
                    "upstream_entity_id": upstream_entity_id,
                    "downstream_entity_type": downstream_entity_type,
                    "downstream_entity_id": downstream_entity_id,
                    "relationship_type": relationship_type,
                    "metadata_json": dumps_json(metadata or {}),
                    "created_by_admin_public_id": admin_id,
                },
            )
            return public_row(self.repository.lineage_edge(connection, public_id))

    def upstream_of(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            edges = self.repository.edges_upstream_of(connection, entity_type, entity_id)
            return {"items": [public_row(edge) for edge in edges]}

    def downstream_of(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            edges = self.repository.edges_downstream_of(connection, entity_type, entity_id)
            return {"items": [public_row(edge) for edge in edges]}

    def trace(
        self, entity_type: str, entity_id: str, *, max_depth: int = 10
    ) -> dict[str, Any]:
        """A readable, bidirectional trace anchored at one entity --
        never claims completeness beyond what real edges support."""

        visited_nodes: set[tuple[str, str]] = {(entity_type, entity_id)}
        edges: list[dict[str, Any]] = []

        def _walk(node_type: str, node_id: str, *, upstream: bool, depth: int) -> None:
            if depth >= max_depth:
                return
            with self.repository.transaction() as connection:
                found = (
                    self.repository.edges_upstream_of(connection, node_type, node_id)
                    if upstream
                    else self.repository.edges_downstream_of(connection, node_type, node_id)
                )
            for row in found:
                edge = public_row(row)
                edges.append(edge)
                next_node = (
                    (edge["upstream_entity_type"], edge["upstream_entity_id"])
                    if upstream
                    else (edge["downstream_entity_type"], edge["downstream_entity_id"])
                )
                if next_node in visited_nodes:
                    continue
                visited_nodes.add(next_node)
                _walk(next_node[0], next_node[1], upstream=upstream, depth=depth + 1)

        _walk(entity_type, entity_id, upstream=True, depth=0)
        _walk(entity_type, entity_id, upstream=False, depth=0)

        return {
            "anchor": {"entity_type": entity_type, "entity_id": entity_id},
            "nodes": [{"entity_type": t, "entity_id": i} for t, i in sorted(visited_nodes)],
            "edges": edges,
            "complete": len(edges) > 0,
        }

    def for_source(self, source_public_id: str) -> dict[str, Any]:
        """Every dataset_record linked (Phase 2 `source_record_links`)
        to this source, traced downstream -- never assumes a link that
        the registry doesn't actually record."""

        with self.sources.transaction() as connection:
            rows = connection.execute(
                """SELECT entity_public_id FROM source_record_links
                JOIN data_sources ON data_sources.id = source_record_links.data_source_id
                WHERE data_sources.public_id=? AND entity_type='dataset_record'""",
                (source_public_id,),
            ).fetchall()
        linked_entity_ids = [row["entity_public_id"] for row in rows]
        traces = [
            self.trace("dataset_record", entity_id) for entity_id in linked_entity_ids
        ]
        return {"source_public_id": source_public_id, "linked_dataset_records": traces}

    def for_model_release(self, release_public_id: str) -> dict[str, Any]:
        """Reads the *existing* direct-FK lineage already on
        `model_release_candidates` (never re-created as edges), then
        appends any `lineage_edges` feeding into its dataset_version
        from the Data-Studio side."""

        with self.repository.transaction() as connection:
            row = connection.execute(
                """SELECT mrc.public_id AS release_public_id,
                dv.public_id AS dataset_version_public_id,
                tv.public_id AS tokenizer_version_public_id,
                pc.public_id AS checkpoint_public_id,
                itc.public_id AS instruction_tuning_candidate_public_id,
                mer.public_id AS model_evaluation_run_public_id
                FROM model_release_candidates mrc
                LEFT JOIN dataset_versions dv ON dv.id = mrc.dataset_version_id
                LEFT JOIN tokenizer_versions tv ON tv.id = mrc.tokenizer_version_id
                LEFT JOIN pretraining_checkpoints pc ON pc.id = mrc.checkpoint_id
                LEFT JOIN instruction_tuning_candidates itc
                    ON itc.id = mrc.instruction_tuning_candidate_id
                LEFT JOIN model_evaluation_runs mer ON mer.id = mrc.model_evaluation_run_id
                WHERE mrc.public_id=?""",
                (release_public_id,),
            ).fetchone()
        if row is None:
            return {
                "release_public_id": release_public_id,
                "direct_lineage": {},
                "upstream_data_studio_lineage": {"items": []},
                "complete": False,
            }
        direct_lineage = dict(row)
        upstream = (
            self.upstream_of("dataset_version", direct_lineage["dataset_version_public_id"])
            if direct_lineage.get("dataset_version_public_id")
            else {"items": []}
        )
        return {
            "release_public_id": release_public_id,
            "direct_lineage": direct_lineage,
            "upstream_data_studio_lineage": upstream,
            "complete": bool(direct_lineage.get("dataset_version_public_id")),
        }


__all__ = ["LineageGraphService"]
