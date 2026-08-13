"""Repository for MB-08: Brud Mini Brain Continuous Learning &
Feedback Engine.

`mini_brain_continuous_learning_sessions`/`_events` are MB-08's OWN
state only. MB-08 never writes to any other system's tables -- every
analysis stage reads real data from Public Chat routing/feedback
events and the Knowledge Gap Registry through their own existing
read-only methods, and only ever persists its own derived reports
here.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {"id"}
JSON_FIELDS = (
    "feedback_report", "failure_report", "hallucination_report", "knowledge_gap_report",
    "weak_topic_report", "difficulty_report", "dataset_recommendation_report",
    "training_recommendation_report", "priority_report", "continuous_learning_report",
)


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("mini brain continuous learning session row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class MiniBrainContinuousLearningRepository(BaseRepository):
    def create_session(
        self, connection: sqlite3.Connection, *, cycle_window_days: int,
        created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_continuous_learning_sessions(
                public_id, cycle_window_days, created_by_admin_public_id
            ) VALUES (?, ?, ?)""",
            (public_id, cycle_window_days, created_by_admin_public_id),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_continuous_learning_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"continuous learning session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_continuous_learning_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def update_session(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any],
    ) -> sqlite3.Row:
        self.session(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        json_columns = {f"{f}_json" for f in JSON_FIELDS}
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column in json_columns else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_continuous_learning_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    def record_event(
        self, connection: sqlite3.Connection, *, learning_cycle_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_continuous_learning_events(
                public_id, learning_cycle_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, learning_cycle_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, learning_cycle_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_continuous_learning_events WHERE learning_cycle_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (learning_cycle_session_id, limit, offset),
        ).fetchall()
