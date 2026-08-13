"""Repository for MB-26: Brud Mini Brain Voice & Speech Runtime.

Five tables, all MB-26's own: `mini_brain_voice_sessions`,
`mini_brain_voice_messages` (sanitized text only, never audio bytes),
`mini_brain_voice_permissions` (per-session consent/authorization
record), `mini_brain_voice_runtime_events` (append-only), and
`mini_brain_voice_runtime_memory` (permanent, insert-only). MB-26
never writes to any other system's tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
_MESSAGE_INTERNAL = {"id", "session_id"}
_PERMISSION_INTERNAL = {"id", "session_id"}
_EVENT_INTERNAL = {"id", "session_id"}
_MEMORY_INTERNAL = {"id", "session_id"}


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("voice session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key == "consent_given":
            data[key] = bool(data[key])
    return data


def public_message_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("voice message row not found")
    data = dict(row)
    for key in list(data):
        if key in _MESSAGE_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
        elif key == "truncated":
            data[key] = bool(data[key])
    return data


def public_permission_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("voice permission row not found")
    data = dict(row)
    for key in list(data):
        if key in _PERMISSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
        elif key in ("explicit_consent_given", "admin_authorized"):
            data[key] = bool(data[key])
    return data


def public_event_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("voice runtime event row not found")
    data = dict(row)
    for key in list(data):
        if key in _EVENT_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("voice runtime memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL:
            data.pop(key)
    return data


class MiniBrainVoiceRuntimeRepository(BaseRepository):
    # -- sessions ------------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, session_mode: str,
        conversation_id: str | None, requester_user_id_hash: str | None,
        requester_admin_public_id: str | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_voice_sessions(
                public_id, session_mode, conversation_id, requester_user_id_hash, requester_admin_public_id
            ) VALUES (?, ?, ?, ?, ?)""",
            (public_id, session_mode, conversation_id, requester_user_id_hash, requester_admin_public_id),
        )
        return public_id

    def get_session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_voice_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"voice session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
        status: str | None = None, session_mode: str | None = None,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        clauses = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if session_mode:
            clauses.append("session_mode=?")
            params.append(session_mode)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        return connection.execute(
            f"SELECT * FROM mini_brain_voice_sessions {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params,
        ).fetchall()

    def update_session(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any]
    ) -> sqlite3.Row:
        self.get_session(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(int(value) if isinstance(value, bool) else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_voice_sessions SET {", ".join(set_clauses)} WHERE public_id=?', values,
        )
        return self.get_session(connection, public_id)

    # -- messages (sanitized text only) --------------------------------------

    def create_message(
        self, connection: sqlite3.Connection, *, session_id: int, message_type: str,
        sanitized_text: str, redaction_categories: list[str], truncated: bool,
        audio_hash: str | None = None, audio_duration_ms: float | None = None,
        tts_audio_relative_path: str | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_voice_messages(
                public_id, session_id, message_type, sanitized_text, redaction_categories_json,
                truncated, audio_hash, audio_duration_ms, tts_audio_relative_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, session_id, message_type, sanitized_text, dumps_json(redaction_categories),
                int(truncated), audio_hash, audio_duration_ms, tts_audio_relative_path,
            ),
        )
        return public_id

    def list_messages(
        self, connection: sqlite3.Connection, *, session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_voice_messages WHERE session_id=? ORDER BY id LIMIT ? OFFSET ?",
            (session_id, limit, offset),
        ).fetchall()

    # -- permissions -----------------------------------------------------------

    def create_permission(
        self, connection: sqlite3.Connection, *, session_id: int, scope_key: str, decision: str,
        reason: str | None, explicit_consent_given: bool, admin_authorized: bool,
        mb24_decision: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_voice_permissions(
                public_id, session_id, scope_key, decision, reason,
                explicit_consent_given, admin_authorized, mb24_decision_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, session_id, scope_key, decision, reason,
                int(explicit_consent_given), int(admin_authorized), dumps_json(mb24_decision or {}),
            ),
        )
        return public_id

    def list_permissions(
        self, connection: sqlite3.Connection, *, session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_voice_permissions WHERE session_id=? ORDER BY id LIMIT ? OFFSET ?",
            (session_id, limit, offset),
        ).fetchall()

    # -- runtime events (append-only) -------------------------------------------

    def create_event(
        self, connection: sqlite3.Connection, *, session_id: int | None, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_voice_runtime_events(
                public_id, session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, session_id: int | None = None, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if session_id is not None:
            return connection.execute(
                """SELECT * FROM mini_brain_voice_runtime_events WHERE session_id=?
                ORDER BY id DESC LIMIT ? OFFSET ?""",
                (session_id, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_voice_runtime_events ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- runtime memory (permanent, insert-only) -------------------------------------

    def create_memory(
        self, connection: sqlite3.Connection, *, session_id: int, session_mode: str, final_status: str,
        stt_backend_used: str | None, tts_backend_used: str | None, duration_ms: float | None,
        total_chunks: int, total_audio_bytes: int, recorded_by: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_voice_runtime_memory(
                public_id, session_id, session_mode, final_status, stt_backend_used, tts_backend_used,
                duration_ms, total_chunks, total_audio_bytes, recorded_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, session_id, session_mode, final_status, stt_backend_used, tts_backend_used,
                duration_ms, total_chunks, total_audio_bytes, recorded_by,
            ),
        )
        return public_id

    def list_memory(self, connection: sqlite3.Connection, *, limit: int, offset: int) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_voice_runtime_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- statistics --------------------------------------------------------------

    def statistics(self, connection: sqlite3.Connection) -> dict[str, Any]:
        total = connection.execute("SELECT COUNT(*) AS n FROM mini_brain_voice_sessions").fetchone()["n"]
        by_status_rows = connection.execute(
            "SELECT status, COUNT(*) AS n FROM mini_brain_voice_sessions GROUP BY status"
        ).fetchall()
        return {
            "total_sessions": total,
            "sessions_by_status": {row["status"]: row["n"] for row in by_status_rows},
        }


__all__ = [
    "MiniBrainVoiceRuntimeRepository",
    "public_session_row",
    "public_message_row",
    "public_permission_row",
    "public_event_row",
    "public_memory_row",
]
