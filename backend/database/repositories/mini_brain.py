"""Repository for MB-01: Brud Mini Brain foundation.

Deliberately its own repository, not a method added to any existing
one -- `mini_brain_settings`/`mini_brain_events` have no foreign key
to any Admin Assistant or inference-runtime table, keeping this
module's storage genuinely independent.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {"id"}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("mini brain row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key == "enabled":
            data[key] = bool(data[key])
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class MiniBrainRepository(BaseRepository):
    def ensure_settings_row(self, connection: sqlite3.Connection) -> sqlite3.Row:
        """MB-01 ships with the module disabled and unconfigured -- the
        settings row is created lazily on first access rather than
        seeded by the migration, so a fresh database has no opinion
        about whether Mini Brain should be on."""

        row = connection.execute("SELECT * FROM mini_brain_settings LIMIT 1").fetchone()
        if row is not None:
            return row
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_settings(public_id, enabled, runtime_status, config_json)
            VALUES (?, 0, 'stopped', '{}')""",
            (public_id,),
        )
        return connection.execute(
            "SELECT * FROM mini_brain_settings WHERE public_id=?", (public_id,)
        ).fetchone()

    def update_settings(
        self, connection: sqlite3.Connection, *, fields: dict[str, Any], admin_public_id: str | None
    ) -> sqlite3.Row:
        current = self.ensure_settings_row(connection)
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column == "config_json" else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        set_clauses.append('"updated_by_admin_public_id"=?')
        values.append(admin_public_id)
        values.append(current["public_id"])
        connection.execute(
            f'UPDATE mini_brain_settings SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return connection.execute(
            "SELECT * FROM mini_brain_settings WHERE public_id=?", (current["public_id"],)
        ).fetchone()

    def record_event(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        level: str = "info",
        message: str,
        details: dict[str, Any] | None = None,
        actor_admin_public_id: str | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_events(
                public_id, event_type, level, message, details_json, actor_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, event_type, level, message, dumps_json(details or {}), actor_admin_public_id),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, limit: int, offset: int
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_events ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def count_events(self, connection: sqlite3.Connection) -> int:
        return connection.execute("SELECT COUNT(*) FROM mini_brain_events").fetchone()[0]
