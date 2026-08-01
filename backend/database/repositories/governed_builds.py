"""Repository for the Phase 7 (Data Studio) governed build/preflight/
lineage layer: ``governed_build_requests``, ``governed_build_preflight_results``,
``governed_build_request_items``, ``pipeline_artifact_links``,
``lineage_edges``, ``lineage_events``.

This is an *additive* layer above the existing dataset build/versioning
system -- it never writes to ``dataset_versions``/``dataset_version_items``/
``dataset_build_jobs`` directly; those are only ever driven through the
existing ``DatasetVersioningService``. Entities are referenced
polymorphically via ``(entity_type, entity_public_id)``, mirroring
``backend/database/repositories/governance.py``'s convention.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "build_request_id",
    "preflight_result_id",
    "lineage_edge_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("governed build row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class GovernedBuildRepository(BaseRepository):
    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        with super().transaction(immediate=immediate) as connection:
            yield connection

    # --- governed_build_requests --------------------------------------

    def next_build_code(self, connection: sqlite3.Connection) -> str:
        return self._next_code(connection, "governed_build_requests", "build_code", "GBR")

    def create_build_request(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO governed_build_requests(
            public_id, build_code, target_pipeline, build_label, configuration_json,
            requested_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["build_code"],
                values["target_pipeline"],
                values.get("build_label", ""),
                values.get("configuration_json", "{}"),
                values["requested_by_admin_public_id"],
            ),
        )
        return public_id

    def build_request(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM governed_build_requests WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("governed build request not found")
        return row

    def build_request_by_id(self, connection: sqlite3.Connection, request_id: int) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM governed_build_requests WHERE id=?", (request_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("governed build request not found")
        return row

    def list_build_requests(
        self,
        connection: sqlite3.Connection,
        *,
        status: str | None = None,
        target_pipeline: str | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[sqlite3.Row], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if target_pipeline:
            clauses.append("target_pipeline=?")
            params.append(target_pipeline)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = connection.execute(
            f"SELECT COUNT(*) FROM governed_build_requests {where}",  # noqa: S608
            params,
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM governed_build_requests {where} "  # noqa: S608
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return rows, total

    def update_build_request(
        self, connection: sqlite3.Connection, request_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        assignments = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE governed_build_requests SET {assignments},"  # noqa: S608
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), request_id),
        )

    def counts_by_status(self, connection: sqlite3.Connection) -> dict[str, int]:
        rows = connection.execute(
            "SELECT status, COUNT(*) AS count FROM governed_build_requests GROUP BY status"
        ).fetchall()
        return {row["status"]: row["count"] for row in rows}

    # --- governed_build_preflight_results --------------------------------

    def create_preflight_result(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO governed_build_preflight_results(
            public_id, build_request_id, target_pipeline, eligible_count, blocked_count,
            warning_count, excluded_count, decision_summary_json, source_summary_json,
            rights_summary_json, quality_summary_json, duplicate_summary_json,
            conflict_summary_json, language_distribution_json, record_type_distribution_json,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["build_request_id"],
                values["target_pipeline"],
                values.get("eligible_count", 0),
                values.get("blocked_count", 0),
                values.get("warning_count", 0),
                values.get("excluded_count", 0),
                values.get("decision_summary_json", "{}"),
                values.get("source_summary_json", "{}"),
                values.get("rights_summary_json", "{}"),
                values.get("quality_summary_json", "{}"),
                values.get("duplicate_summary_json", "{}"),
                values.get("conflict_summary_json", "{}"),
                values.get("language_distribution_json", "{}"),
                values.get("record_type_distribution_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def preflight_result(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM governed_build_preflight_results WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("preflight result not found")
        return row

    def latest_preflight_result(
        self, connection: sqlite3.Connection, build_request_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM governed_build_preflight_results
            WHERE build_request_id=? ORDER BY id DESC LIMIT 1""",
            (build_request_id,),
        ).fetchone()

    def list_preflight_results(
        self, connection: sqlite3.Connection, build_request_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM governed_build_preflight_results
            WHERE build_request_id=? ORDER BY created_at DESC, id DESC""",
            (build_request_id,),
        ).fetchall()

    # --- governed_build_request_items ------------------------------------

    def create_request_item(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO governed_build_request_items(
            public_id, build_request_id, preflight_result_id, entity_type, entity_public_id,
            entity_revision_public_id, source_public_id, decision, decision_code,
            blocking_reasons_json, warnings_json, included)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["build_request_id"],
                values["preflight_result_id"],
                values["entity_type"],
                values["entity_public_id"],
                values.get("entity_revision_public_id"),
                values.get("source_public_id"),
                values["decision"],
                values["decision_code"],
                values.get("blocking_reasons_json", "[]"),
                values.get("warnings_json", "[]"),
                1 if values.get("included") else 0,
            ),
        )
        return public_id

    def request_item(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM governed_build_request_items WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("build request item not found")
        return row

    def items_for_preflight(
        self, connection: sqlite3.Connection, preflight_result_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM governed_build_request_items
            WHERE preflight_result_id=? ORDER BY id""",
            (preflight_result_id,),
        ).fetchall()

    def items_for_build_request(
        self,
        connection: sqlite3.Connection,
        build_request_id: int,
        *,
        decision: str | None = None,
        included_only: bool = False,
    ) -> list[sqlite3.Row]:
        latest = self.latest_preflight_result(connection, build_request_id)
        if latest is None:
            return []
        query = "SELECT * FROM governed_build_request_items WHERE preflight_result_id=?"
        params: list[Any] = [latest["id"]]
        if decision:
            query += " AND decision=?"
            params.append(decision)
        if included_only:
            query += " AND included=1"
        query += " ORDER BY id"
        return connection.execute(query, params).fetchall()

    def update_request_item(
        self, connection: sqlite3.Connection, item_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        assignments = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE governed_build_request_items SET {assignments} WHERE id=?",  # noqa: S608
            (*fields.values(), item_id),
        )

    def previously_included_entity_ids(
        self,
        connection: sqlite3.Connection,
        *,
        target_pipeline: str,
        entity_type: str,
        entity_public_ids: list[str],
    ) -> set[str]:
        """Step 4's "no previous duplicate export for the same target" --
        only counts entities included in a *completed* prior build for
        this exact target pipeline."""

        if not entity_public_ids:
            return set()
        placeholders = ",".join("?" for _ in entity_public_ids)
        rows = connection.execute(
            f"""SELECT DISTINCT i.entity_public_id FROM governed_build_request_items i
            JOIN governed_build_requests r ON r.id = i.build_request_id
            WHERE r.target_pipeline=? AND r.status='completed' AND i.included=1
            AND i.entity_type=? AND i.entity_public_id IN ({placeholders})""",  # noqa: S608
            (target_pipeline, entity_type, *entity_public_ids),
        ).fetchall()
        return {row["entity_public_id"] for row in rows}

    def prior_evaluation_entity_ids(
        self, connection: sqlite3.Connection, *, entity_type: str = "dataset_record"
    ) -> frozenset[str]:
        """Every entity ever included in a completed evaluation-target
        build -- used to keep evaluation content out of train/validation
        splits of any other build (Step 8/17)."""

        rows = connection.execute(
            """SELECT DISTINCT i.entity_public_id FROM governed_build_request_items i
            JOIN governed_build_requests r ON r.id = i.build_request_id
            WHERE r.target_pipeline='evaluation' AND r.status='completed'
            AND i.included=1 AND i.entity_type=?""",
            (entity_type,),
        ).fetchall()
        return frozenset(row["entity_public_id"] for row in rows)

    # --- pipeline_artifact_links -------------------------------------------

    def create_artifact_link(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO pipeline_artifact_links(
            public_id, build_request_id, artifact_type, artifact_public_id,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            (
                public_id,
                values["build_request_id"],
                values["artifact_type"],
                values["artifact_public_id"],
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def artifact_links_for_request(
        self, connection: sqlite3.Connection, build_request_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM pipeline_artifact_links WHERE build_request_id=? ORDER BY id",
            (build_request_id,),
        ).fetchall()

    def find_links_by_artifact(
        self, connection: sqlite3.Connection, artifact_type: str, artifact_public_id: str
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM pipeline_artifact_links
            WHERE artifact_type=? AND artifact_public_id=? ORDER BY id""",
            (artifact_type, artifact_public_id),
        ).fetchall()

    # --- lineage_edges -------------------------------------------------------

    def create_lineage_edge(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        existing = connection.execute(
            """SELECT public_id FROM lineage_edges WHERE upstream_entity_type=?
            AND upstream_entity_id=? AND downstream_entity_type=? AND downstream_entity_id=?
            AND relationship_type=?""",
            (
                values["upstream_entity_type"],
                values["upstream_entity_id"],
                values["downstream_entity_type"],
                values["downstream_entity_id"],
                values["relationship_type"],
            ),
        ).fetchone()
        if existing:
            return existing["public_id"]
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO lineage_edges(
            public_id, upstream_entity_type, upstream_entity_id, downstream_entity_type,
            downstream_entity_id, relationship_type, metadata_json, created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["upstream_entity_type"],
                values["upstream_entity_id"],
                values["downstream_entity_type"],
                values["downstream_entity_id"],
                values["relationship_type"],
                values.get("metadata_json", "{}"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def lineage_edge(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM lineage_edges WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("lineage edge not found")
        return row

    def edges_upstream_of(
        self, connection: sqlite3.Connection, entity_type: str, entity_id: str
    ) -> list[sqlite3.Row]:
        """Edges where `(entity_type, entity_id)` is the *downstream*
        side -- i.e. what feeds into this entity."""

        return connection.execute(
            """SELECT * FROM lineage_edges
            WHERE downstream_entity_type=? AND downstream_entity_id=?
            ORDER BY created_at DESC, id DESC""",
            (entity_type, entity_id),
        ).fetchall()

    def edges_downstream_of(
        self, connection: sqlite3.Connection, entity_type: str, entity_id: str
    ) -> list[sqlite3.Row]:
        """Edges where `(entity_type, entity_id)` is the *upstream* side
        -- i.e. what this entity feeds into."""

        return connection.execute(
            """SELECT * FROM lineage_edges
            WHERE upstream_entity_type=? AND upstream_entity_id=?
            ORDER BY created_at DESC, id DESC""",
            (entity_type, entity_id),
        ).fetchall()

    # --- lineage_events ---------------------------------------------------

    def create_lineage_event(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO lineage_events(
            public_id, build_request_id, lineage_edge_id, event_type,
            performed_by_admin_public_id, notes, metadata_json)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                values.get("build_request_id"),
                values.get("lineage_edge_id"),
                values["event_type"],
                values["performed_by_admin_public_id"],
                values.get("notes", ""),
                values.get("metadata_json", "{}"),
            ),
        )
        return public_id

    def lineage_events_for_request(
        self, connection: sqlite3.Connection, build_request_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM lineage_events WHERE build_request_id=?
            ORDER BY created_at DESC, id DESC""",
            (build_request_id,),
        ).fetchall()

    # --- candidate dataset_records (read-only; never writes to dataset_records)

    def candidate_dataset_records(
        self,
        connection: sqlite3.Connection,
        *,
        record_types: list[str] | None = None,
        languages: list[str] | None = None,
        source_public_ids: list[str] | None = None,
        include_entity_ids: list[str] | None = None,
        exclude_entity_ids: list[str] | None = None,
        limit: int = 5000,
    ) -> list[sqlite3.Row]:
        """Broader, multi-value candidate query than the existing
        `DatasetQualityRepository.selectable_records()` (which only
        supports single-value filters) -- read-only, and never used by
        the existing dataset build path, so `selectable_records()`
        itself stays untouched for every existing caller. Domain
        filtering (from `metadata_json.domain`) is applied by the
        caller in Python, since it isn't a plain column."""

        clauses = [
            "r.status='approved'",
            "(s.licence_status IS NULL OR s.licence_status<>'rejected')",
        ]
        params: list[Any] = []
        if record_types:
            placeholders = ",".join("?" for _ in record_types)
            clauses.append(f"r.record_type IN ({placeholders})")
            params.extend(record_types)
        if languages:
            placeholders = ",".join("?" for _ in languages)
            clauses.append(f"r.language IN ({placeholders})")
            params.extend(languages)
        if source_public_ids:
            placeholders = ",".join("?" for _ in source_public_ids)
            clauses.append(f"s.public_id IN ({placeholders})")
            params.extend(source_public_ids)
        if include_entity_ids:
            placeholders = ",".join("?" for _ in include_entity_ids)
            clauses.append(f"r.public_id IN ({placeholders})")
            params.extend(include_entity_ids)
        if exclude_entity_ids:
            placeholders = ",".join("?" for _ in exclude_entity_ids)
            clauses.append(f"r.public_id NOT IN ({placeholders})")
            params.extend(exclude_entity_ids)
        rows = connection.execute(
            f"""SELECT r.*, s.public_id AS source_public_id, s.source_type, s.licence_status,
            s.name AS source_name FROM dataset_records r
            LEFT JOIN dataset_sources s ON s.id = r.source_id
            WHERE {" AND ".join(clauses)}
            ORDER BY r.content_hash, r.public_id LIMIT ?""",  # noqa: S608
            (*params, limit),
        ).fetchall()
        return list(rows)

    # --- shared helpers ------------------------------------------------------

    def _next_code(
        self, connection: sqlite3.Connection, table: str, column: str, prefix: str
    ) -> str:
        rows = connection.execute(
            f"SELECT {column} FROM {table} WHERE {column} LIKE ?",  # noqa: S608
            (f"{prefix}-%",),
        ).fetchall()
        max_number = 0
        for row in rows:
            suffix = row[0].removeprefix(f"{prefix}-")
            if suffix.isdigit():
                max_number = max(max_number, int(suffix))
        return f"{prefix}-{max_number + 1:04d}"
