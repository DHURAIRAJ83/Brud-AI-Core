"""Repository for MB-12: Brud Mini Brain Autonomous AI Knowledge
Pipeline Coordinator.

Two tables, both MB-12's own: `mini_brain_pipeline_sessions` and
`mini_brain_pipeline_events` (append-only, immutability triggers).
MB-12 never writes to any other system's tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
SESSION_JSON_FIELDS = (
    "pipeline_manager_report", "rag_first_report", "training_readiness_report",
    "lifecycle_timeline", "improvement_prediction", "recommendation_report", "master_report",
)


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("pipeline session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class MiniBrainPipelineCoordinatorRepository(BaseRepository):
    def create_session(
        self, connection: sqlite3.Connection, *, topic: str, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_pipeline_sessions(
                public_id, topic, created_by_admin_public_id
            ) VALUES (?, ?, ?)""",
            (public_id, topic, created_by_admin_public_id),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_pipeline_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"pipeline session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_pipeline_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
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
            f'UPDATE mini_brain_pipeline_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    def record_event(
        self, connection: sqlite3.Connection, *, pipeline_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_pipeline_events(
                public_id, pipeline_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, pipeline_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, pipeline_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_pipeline_events WHERE pipeline_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (pipeline_session_id, limit, offset),
        ).fetchall()


__all__ = ["MiniBrainPipelineCoordinatorRepository", "public_session_row", "SESSION_JSON_FIELDS"]
