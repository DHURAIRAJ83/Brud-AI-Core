"""Repository for MB-25: Brud Mini Brain Secure Plugin Execution
Runtime.

Four tables, all MB-25's own: `mini_brain_plugin_runtime_executions`,
`mini_brain_plugin_runtime_io` (sanitized input/output only),
`mini_brain_plugin_runtime_execution_events` (append-only -- renamed
from the spec's own `..._events` to avoid a direct collision with
MB-24's own, pre-existing `mini_brain_plugin_runtime_events` table),
and `mini_brain_plugin_runtime_execution_memory` (permanent,
insert-only -- renamed for the same reason). MB-25 never writes to any
other system's tables, including MB-24's own.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_EXECUTION_INTERNAL = {"id"}
EXECUTION_JSON_FIELDS = ("arguments", "granted_scopes")
_IO_INTERNAL = {"id", "execution_id"}
_MEMORY_INTERNAL = {"id", "execution_id"}


def public_execution_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("plugin runtime execution row not found")
    data = dict(row)
    for key in list(data):
        if key in _EXECUTION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_io_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("plugin runtime io row not found")
    data = dict(row)
    for key in list(data):
        if key in _IO_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
        elif key == "truncated":
            data[key] = bool(data[key])
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("plugin runtime execution memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL:
            data.pop(key)
    return data


class MiniBrainPluginRuntimeExecutionRepository(BaseRepository):
    # -- executions ------------------------------------------------------------

    def create_execution(
        self, connection: sqlite3.Connection, *, plugin_public_id: str, execution_mode: str, scope_key: str,
        arguments: dict[str, Any], granted_scopes: list[str], requester_user_id_hash: str | None,
        requester_admin_public_id: str | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_plugin_runtime_executions(
                public_id, plugin_public_id, execution_mode, scope_key, arguments_json, granted_scopes_json,
                requester_user_id_hash, requester_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, plugin_public_id, execution_mode, scope_key, dumps_json(arguments),
                dumps_json(granted_scopes), requester_user_id_hash, requester_admin_public_id,
            ),
        )
        return public_id

    def get_execution(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_plugin_runtime_executions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"plugin runtime execution not found: {public_id}")
        return row

    def list_executions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int, status: str | None = None,
        plugin_public_id: str | None = None,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        clauses = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if plugin_public_id:
            clauses.append("plugin_public_id=?")
            params.append(plugin_public_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        return connection.execute(
            f"SELECT * FROM mini_brain_plugin_runtime_executions {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()

    def update_execution(self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any]) -> sqlite3.Row:
        self.get_execution(connection, public_id)
        json_columns = {f"{f}_json" for f in EXECUTION_JSON_FIELDS}
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column in json_columns else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_plugin_runtime_executions SET {", ".join(set_clauses)} WHERE public_id=?', values,
        )
        return self.get_execution(connection, public_id)

    # -- sanitized io ------------------------------------------------------------

    def create_io(
        self, connection: sqlite3.Connection, *, execution_id: int, io_type: str, sanitized_payload: dict[str, Any],
        truncated: bool, redaction_categories: list[str],
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_plugin_runtime_io(
                public_id, execution_id, io_type, sanitized_payload_json, truncated, redaction_categories_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, execution_id, io_type, dumps_json(sanitized_payload), int(truncated), dumps_json(redaction_categories)),
        )
        return public_id

    def list_io(self, connection: sqlite3.Connection, *, execution_id: int, limit: int, offset: int) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_plugin_runtime_io WHERE execution_id=? ORDER BY id LIMIT ? OFFSET ?",
            (execution_id, limit, offset),
        ).fetchall()

    # -- execution events (append-only) ---------------------------------------------

    def create_event(
        self, connection: sqlite3.Connection, *, execution_id: int | None, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_plugin_runtime_execution_events(
                public_id, execution_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, execution_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, execution_id: int | None = None, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if execution_id is not None:
            return connection.execute(
                """SELECT * FROM mini_brain_plugin_runtime_execution_events WHERE execution_id=?
                ORDER BY id DESC LIMIT ? OFFSET ?""",
                (execution_id, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_plugin_runtime_execution_events ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- execution memory (permanent, insert-only) -----------------------------------

    def create_memory(
        self, connection: sqlite3.Connection, *, execution_id: int, plugin_public_id: str, final_status: str,
        duration_ms: float | None, guard_violation_count: int, recorded_by: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_plugin_runtime_execution_memory(
                public_id, execution_id, plugin_public_id, final_status, duration_ms, guard_violation_count, recorded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (public_id, execution_id, plugin_public_id, final_status, duration_ms, guard_violation_count, recorded_by),
        )
        return public_id

    def list_memory(self, connection: sqlite3.Connection, *, limit: int, offset: int) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_plugin_runtime_execution_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- statistics --------------------------------------------------------------

    def statistics(self, connection: sqlite3.Connection) -> dict[str, Any]:
        total = connection.execute("SELECT COUNT(*) AS n FROM mini_brain_plugin_runtime_executions").fetchone()["n"]
        by_status_rows = connection.execute(
            "SELECT status, COUNT(*) AS n FROM mini_brain_plugin_runtime_executions GROUP BY status"
        ).fetchall()
        avg_duration_row = connection.execute(
            "SELECT AVG(duration_ms) AS avg_ms FROM mini_brain_plugin_runtime_executions WHERE duration_ms IS NOT NULL"
        ).fetchone()
        return {
            "total_executions": total, "executions_by_status": {row["status"]: row["n"] for row in by_status_rows},
            "average_duration_ms": avg_duration_row["avg_ms"],
        }


__all__ = [
    "MiniBrainPluginRuntimeExecutionRepository", "public_execution_row", "public_io_row", "public_memory_row",
    "EXECUTION_JSON_FIELDS",
]
