"""Repository for MB-30: Production Runtime Manager & One-Click Local
Model Lifecycle.

Four tables, all MB-30's own: `mini_brain_model_installations`,
`mini_brain_model_runtime` (one row per load/benchmark event, a
history log, not a singleton), `mini_brain_runtime_events`
(append-only), `mini_brain_runtime_memory` (permanent, insert-only).
MB-30 never writes to any other system's tables -- including MB-04's
unrelated, pre-existing runtime-lifecycle tables/service.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_INSTALLATION_INTERNAL = {"id"}
_RUNTIME_INTERNAL = {"id"}
_EVENT_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_installation_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("model installation row not found")
    data = dict(row)
    for key in list(data):
        if key in _INSTALLATION_INTERNAL:
            data.pop(key)
    return data


def public_runtime_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("model runtime row not found")
    data = dict(row)
    for key in list(data):
        if key in _RUNTIME_INTERNAL:
            data.pop(key)
        elif key == "loaded":
            data[key] = bool(data[key])
    return data


def public_event_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("runtime event row not found")
    data = dict(row)
    for key in list(data):
        if key in _EVENT_INTERNAL:
            data.pop(key)
        elif key == "detail_json":
            data["detail"] = loads_json(data.pop(key))
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("runtime memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL:
            data.pop(key)
    return data


class MiniBrainRuntimeManagerRepository(BaseRepository):
    # -- installations -----------------------------------------------------------------

    def create_installation(
        self, connection: sqlite3.Connection, *, model_name: str, family: str | None, quantization: str | None,
        file_name: str, install_path: str, file_size_bytes: int | None, sha256: str | None, status: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_model_installations(
                public_id, model_name, family, quantization, file_name, install_path,
                file_size_bytes, sha256, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (public_id, model_name, family, quantization, file_name, install_path, file_size_bytes, sha256, status),
        )
        return public_id

    def get_installation(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_model_installations WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"model installation not found: {public_id}")
        return row

    def latest_installation_for_model(self, connection: sqlite3.Connection, model_name: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM mini_brain_model_installations WHERE model_name=? ORDER BY id DESC LIMIT 1",
            (model_name,),
        ).fetchone()

    def list_installations(
        self, connection: sqlite3.Connection, *, status: str | None = None, limit: int = 100, offset: int = 0,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if status:
            return connection.execute(
                "SELECT * FROM mini_brain_model_installations WHERE status=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_model_installations ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
        ).fetchall()

    def update_installation(self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any]) -> sqlite3.Row:
        self.get_installation(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_model_installations SET {", ".join(set_clauses)} WHERE public_id=?', values,
        )
        return self.get_installation(connection, public_id)

    # -- runtime (history log) ----------------------------------------------------------

    def create_runtime_row(
        self, connection: sqlite3.Connection, *, model_name: str, loaded: bool, backend: str,
        context_length: int | None, max_tokens: int | None, temperature: float | None, threads: int | None,
        load_time_ms: float | None, peak_ram_mb: float | None, tokens_per_second: float | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_model_runtime(
                public_id, model_name, loaded, backend, context_length, max_tokens, temperature, threads,
                load_time_ms, last_used_at, peak_ram_mb, tokens_per_second
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)""",
            (
                public_id, model_name, int(loaded), backend, context_length, max_tokens, temperature, threads,
                load_time_ms, peak_ram_mb, tokens_per_second,
            ),
        )
        return public_id

    def latest_runtime_row(self, connection: sqlite3.Connection) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM mini_brain_model_runtime ORDER BY id DESC LIMIT 1"
        ).fetchone()

    def list_runtime_history(
        self, connection: sqlite3.Connection, *, model_name: str | None = None, limit: int = 50, offset: int = 0,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if model_name:
            return connection.execute(
                "SELECT * FROM mini_brain_model_runtime WHERE model_name=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (model_name, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_model_runtime ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
        ).fetchall()

    # -- runtime events (append-only) ----------------------------------------------------

    def create_event(
        self, connection: sqlite3.Connection, *, model_name: str | None, event_type: str,
        admin_id: str | None, detail: dict[str, Any],
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_runtime_events(
                public_id, model_name, event_type, admin_id, detail_json
            ) VALUES (?, ?, ?, ?, ?)""",
            (public_id, model_name, event_type, admin_id, dumps_json(detail)),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, model_name: str | None = None, limit: int = 100, offset: int = 0,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if model_name:
            return connection.execute(
                "SELECT * FROM mini_brain_runtime_events WHERE model_name=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (model_name, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_runtime_events ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
        ).fetchall()

    # -- runtime memory (permanent, insert-only) -------------------------------------------

    def create_memory(
        self, connection: sqlite3.Connection, *, model_name: str | None, event_type: str, admin_id: str | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_runtime_memory(
                public_id, model_name, event_type, admin_id
            ) VALUES (?, ?, ?, ?)""",
            (public_id, model_name, event_type, admin_id),
        )
        return public_id

    def list_memory(self, connection: sqlite3.Connection, *, limit: int = 50, offset: int = 0) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_runtime_memory ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainRuntimeManagerRepository",
    "public_installation_row",
    "public_runtime_row",
    "public_event_row",
    "public_memory_row",
]
