"""Repository for MB-11: Brud Mini Brain Autonomous Dataset Evolution &
Knowledge Factory.

Two tables, both MB-11's own: `mini_brain_dataset_evolution_sessions`
and `mini_brain_dataset_evolution_events` (append-only, immutability
triggers). MB-11 never writes to any other system's tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
SESSION_JSON_FIELDS = (
    "evolution_analysis", "dependency_graph", "coverage_report", "relationship_report",
    "expansion_plan", "version_plan", "knowledge_factory_plan", "synthetic_dataset_plan",
    "quality_evolution", "simulation_report", "recommendation_report", "evolution_report",
    "rag_report",
)


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("dataset evolution session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class MiniBrainDatasetEvolutionRepository(BaseRepository):
    def create_session(
        self, connection: sqlite3.Connection, *, dataset_source_public_id: str, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_dataset_evolution_sessions(
                public_id, dataset_source_public_id, created_by_admin_public_id
            ) VALUES (?, ?, ?)""",
            (public_id, dataset_source_public_id, created_by_admin_public_id),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_dataset_evolution_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"dataset evolution session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_dataset_evolution_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def update_session(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any],
    ) -> sqlite3.Row:
        self.session(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        json_columns = {f"{f}_json" for f in SESSION_JSON_FIELDS}
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column in json_columns else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_dataset_evolution_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    def record_event(
        self, connection: sqlite3.Connection, *, evolution_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_dataset_evolution_events(
                public_id, evolution_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, evolution_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, evolution_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_dataset_evolution_events WHERE evolution_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (evolution_session_id, limit, offset),
        ).fetchall()


__all__ = ["MiniBrainDatasetEvolutionRepository", "public_session_row", "SESSION_JSON_FIELDS"]
