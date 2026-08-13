"""Repository for MB-09: Brud Mini Brain Continuous Learning Center.

Three tables, all MB-09's own: `mini_brain_learning_memory` (permanent,
insert-only), `mini_brain_continuous_learning_center_sessions`, and
`mini_brain_continuous_learning_center_events`. MB-09 never writes to
any other system's tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
SESSION_JSON_FIELDS = (
    "knowledge_gap_evolution_report", "learning_queue_report", "draft_report",
    "provider_request", "provider_consensus_report", "dataset_evolution_report",
    "roadmap_report", "recommendation_report", "planning_report",
)
_MEMORY_INTERNAL = {"id"}
_MEMORY_JSON_FIELDS = ("weak_domains", "strong_domains", "benchmark_summary")


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("continuous learning center session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("learning memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class MiniBrainContinuousLearningCenterRepository(BaseRepository):
    # -- learning memory (permanent, insert-only) ------------------------------

    def record_memory(
        self, connection: sqlite3.Connection, *, continuous_learning_session_public_id: str,
        model_version_public_id: str | None, dataset_version_public_id: str | None,
        weak_domains: list[str], strong_domains: list[str], training_decision: str | None,
        benchmark_summary: dict[str, Any], admin_decision: str | None, improvement_notes: str,
        recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_learning_memory(
                public_id, continuous_learning_session_public_id, model_version_public_id,
                dataset_version_public_id, weak_domains_json, strong_domains_json,
                training_decision, benchmark_summary_json, admin_decision, improvement_notes,
                recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, continuous_learning_session_public_id, model_version_public_id,
                dataset_version_public_id, dumps_json(weak_domains), dumps_json(strong_domains),
                training_decision, dumps_json(benchmark_summary), admin_decision, improvement_notes,
                recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_memory(
        self, connection: sqlite3.Connection, *, limit: int, offset: int
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_learning_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def get_memory(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_learning_memory WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"learning memory entry not found: {public_id}")
        return row

    # -- center sessions ---------------------------------------------------------

    def create_session(self, connection: sqlite3.Connection, *, created_by_admin_public_id: str) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_continuous_learning_center_sessions(
                public_id, created_by_admin_public_id
            ) VALUES (?, ?)""",
            (public_id, created_by_admin_public_id),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_continuous_learning_center_sessions WHERE public_id=?",
            (public_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"continuous learning center session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_continuous_learning_center_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
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
            f'UPDATE mini_brain_continuous_learning_center_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    def record_event(
        self, connection: sqlite3.Connection, *, center_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_continuous_learning_center_events(
                public_id, center_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, center_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, center_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_continuous_learning_center_events WHERE center_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (center_session_id, limit, offset),
        ).fetchall()
