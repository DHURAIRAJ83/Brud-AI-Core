"""Repository for MB-07: Brud Mini Brain Release Pipeline & Model
Deployment Manager.

`mini_brain_release_sessions`/`mini_brain_release_events` are MB-07's
OWN state only -- every external reference (core model version,
checkpoint, model-release family/candidate/release, rollback plan,
runtime model) is stored as a plain opaque TEXT public_id, never a
foreign key into another system's tables, matching every prior Mini
Brain phase's independence discipline.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {"id"}
JSON_FIELDS = (
    "target_quantizations", "checkpoint_validation_report", "conversion_report",
    "quantization_report", "integrity_report", "compatibility_report",
    "performance_report", "release_report",
)


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("mini brain release session row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class MiniBrainReleaseRepository(BaseRepository):
    def create_session(
        self, connection: sqlite3.Connection, *, core_model_version_public_id: str,
        pretraining_checkpoint_public_id: str, model_release_family_public_id: str,
        target_quantizations: list[str], created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_release_sessions(
                public_id, core_model_version_public_id, pretraining_checkpoint_public_id,
                model_release_family_public_id, target_quantizations_json,
                created_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                public_id, core_model_version_public_id, pretraining_checkpoint_public_id,
                model_release_family_public_id, dumps_json(target_quantizations),
                created_by_admin_public_id,
            ),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_release_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"release session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_release_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
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
            f'UPDATE mini_brain_release_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    def record_event(
        self, connection: sqlite3.Connection, *, release_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_release_events(
                public_id, release_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, release_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, release_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_release_events WHERE release_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (release_session_id, limit, offset),
        ).fetchall()
