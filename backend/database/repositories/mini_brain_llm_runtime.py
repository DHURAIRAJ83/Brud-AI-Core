"""Repository for MB-28: Real Mini Brain LLM Runtime & Admin Assistant
Intelligence Layer.

Four tables, all MB-28's own: `mini_brain_llm_sessions`,
`mini_brain_llm_messages`, `mini_brain_llm_runtime_events`
(append-only), `mini_brain_llm_runtime_memory` (permanent,
insert-only). MB-28 never writes to any other system's tables --
including the separate, pre-existing "Phase 8" Admin Assistant
system's `conversation_sessions`/`conversation_turns`.

`delete_session()` intentionally does not exist -- the API-level
"delete" is always a soft `status="deleted"` transition via
`update_session()`, consistent with this project's append-only-audit
discipline (mirroring MB-27's own "archive" pattern).
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
_MESSAGE_INTERNAL = {"id"}
_EVENT_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("llm session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
    return data


def public_message_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("llm message row not found")
    data = dict(row)
    for key in list(data):
        if key in _MESSAGE_INTERNAL:
            data.pop(key)
        elif key == "tool_call_json":
            raw = data.pop(key)
            data["tool_call"] = loads_json(raw) if raw is not None else None
        elif key == "truncated":
            data[key] = bool(data[key])
    return data


def public_event_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("llm runtime event row not found")
    data = dict(row)
    for key in list(data):
        if key in _EVENT_INTERNAL:
            data.pop(key)
        elif key == "detail_json":
            data["detail"] = loads_json(data.pop(key))
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("llm runtime memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL:
            data.pop(key)
    return data


class MiniBrainLlmRuntimeRepository(BaseRepository):
    # -- sessions --------------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, admin_public_id: str, title: str | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_llm_sessions(
                public_id, admin_public_id, title
            ) VALUES (?, ?, ?)""",
            (public_id, admin_public_id, title),
        )
        return public_id

    def get_session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_llm_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"llm session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, admin_public_id: str | None = None,
        status: str | None = None, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        clauses = []
        params: list[Any] = []
        if admin_public_id:
            clauses.append("admin_public_id=?")
            params.append(admin_public_id)
        if status:
            clauses.append("status=?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        return connection.execute(
            f"SELECT * FROM mini_brain_llm_sessions {where} ORDER BY id DESC LIMIT ? OFFSET ?", params,
        ).fetchall()

    def update_session(self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any]) -> sqlite3.Row:
        self.get_session(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_llm_sessions SET {", ".join(set_clauses)} WHERE public_id=?', values,
        )
        return self.get_session(connection, public_id)

    def count_sessions(self, connection: sqlite3.Connection, *, status: str | None = None) -> int:
        if status:
            return connection.execute(
                "SELECT COUNT(*) FROM mini_brain_llm_sessions WHERE status=?", (status,)
            ).fetchone()[0]
        return connection.execute("SELECT COUNT(*) FROM mini_brain_llm_sessions").fetchone()[0]

    def total_message_count(self, connection: sqlite3.Connection) -> int:
        return connection.execute("SELECT COUNT(*) FROM mini_brain_llm_messages").fetchone()[0]

    # -- messages ----------------------------------------------------------------

    def create_message(
        self, connection: sqlite3.Connection, *, session_id: str, role: str, capability: str,
        sanitized_text: str, backend_type: str | None, tool_call: dict[str, Any] | None,
        truncated: bool, token_estimate: int | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_llm_messages(
                public_id, session_id, role, capability, sanitized_text, backend_type,
                tool_call_json, truncated, token_estimate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, session_id, role, capability, sanitized_text, backend_type,
                dumps_json(tool_call) if tool_call is not None else None, int(truncated), token_estimate,
            ),
        )
        connection.execute(
            """UPDATE mini_brain_llm_sessions
            SET total_messages = total_messages + 1, last_message_at = CURRENT_TIMESTAMP
            WHERE public_id=?""",
            (session_id,),
        )
        return public_id

    def get_message(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_llm_messages WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"llm message not found: {public_id}")
        return row

    def list_messages(
        self, connection: sqlite3.Connection, *, session_id: str, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_llm_messages WHERE session_id=?
            ORDER BY id ASC LIMIT ? OFFSET ?""",
            (session_id, limit, offset),
        ).fetchall()

    # -- runtime events (append-only) ---------------------------------------------

    def create_event(
        self, connection: sqlite3.Connection, *, session_id: str | None, event_type: str,
        backend_type: str | None, admin_id: str | None, detail: dict[str, Any],
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_llm_runtime_events(
                public_id, session_id, event_type, backend_type, admin_id, detail_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, session_id, event_type, backend_type, admin_id, dumps_json(detail)),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, session_id: str | None = None, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if session_id:
            return connection.execute(
                """SELECT * FROM mini_brain_llm_runtime_events WHERE session_id=?
                ORDER BY id DESC LIMIT ? OFFSET ?""",
                (session_id, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_llm_runtime_events ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- runtime memory (permanent, insert-only) -----------------------------------

    def create_memory(
        self, connection: sqlite3.Connection, *, session_id: str, admin_public_id: str,
        event_type: str, backend_type: str | None, total_messages: int,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_llm_runtime_memory(
                public_id, session_id, admin_public_id, event_type, backend_type, total_messages
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, session_id, admin_public_id, event_type, backend_type, total_messages),
        )
        return public_id

    def list_memory(self, connection: sqlite3.Connection, *, limit: int, offset: int) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_llm_runtime_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainLlmRuntimeRepository",
    "public_session_row",
    "public_message_row",
    "public_event_row",
    "public_memory_row",
]
