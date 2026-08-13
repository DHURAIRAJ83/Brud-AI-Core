"""Repository for MB-23: Brud Mini Brain Public Chat Runtime & Self-
Improvement Feedback Loop.

Five tables, all MB-23's own: `mini_brain_public_chat_sessions`,
`mini_brain_public_chat_messages` (append-only, content-hash only --
never raw text), `mini_brain_feedback_signals` (append-only, holds
only already-sanitized `normalized_text`), `mini_brain_improvement_
candidates` (mutable only via `update_candidate()` -- born
`status='pending_admin_review'`), and `mini_brain_public_chat_events`
(append-only audit log). MB-23 never writes to any other system's
tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
_MESSAGE_INTERNAL = {"id", "session_id"}
_SIGNAL_INTERNAL = {"id", "session_id", "message_id"}
CANDIDATE_JSON_FIELDS = ("example_questions", "suggested_missing_knowledge", "handoff_report")


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("public chat session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
    return data


def public_message_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("public chat message row not found")
    data = dict(row)
    for key in list(data):
        if key in _MESSAGE_INTERNAL:
            data.pop(key)
        elif key in ("used_rag", "used_vision", "used_tool"):
            data[key] = bool(data[key])
    return data


def public_signal_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("feedback signal row not found")
    data = dict(row)
    for key in list(data):
        if key in _SIGNAL_INTERNAL:
            data.pop(key)
    return data


def public_candidate_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("improvement candidate row not found")
    data = dict(row)
    for key in list(data):
        if key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
        elif key == "id":
            data.pop(key)
    return data


class MiniBrainPublicChatRuntimeRepository(BaseRepository):
    # -- sessions ------------------------------------------------------------

    def create_session(self, connection: sqlite3.Connection, *, user_session_hash: str, language: str) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_public_chat_sessions(public_id, user_session_hash, language)
            VALUES (?, ?, ?)""",
            (public_id, user_session_hash, language),
        )
        return public_id

    def get_session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_public_chat_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"public chat session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int, status: str | None = None,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if status:
            return connection.execute(
                "SELECT * FROM mini_brain_public_chat_sessions WHERE status=? ORDER BY id DESC LIMIT ? OFFSET ?",
                (status, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_public_chat_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def update_session(self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any]) -> sqlite3.Row:
        self.get_session(connection, public_id)
        set_clauses = [f'"{column}"=?' for column in fields]
        values = list(fields.values())
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_public_chat_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.get_session(connection, public_id)

    # -- messages (append-only) -----------------------------------------------

    def create_message(
        self, connection: sqlite3.Connection, *, session_id: int, role: str, content_hash: str,
        topic_key: str | None, token_estimate: int, used_rag: bool, used_vision: bool, used_tool: bool,
        route_used: str | None, evidence_status: str | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_public_chat_messages(
                public_id, session_id, role, content_hash, topic_key, token_estimate, used_rag, used_vision,
                used_tool, route_used, evidence_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, session_id, role, content_hash, topic_key, token_estimate, int(used_rag),
                int(used_vision), int(used_tool), route_used, evidence_status,
            ),
        )
        return public_id

    def list_messages(
        self, connection: sqlite3.Connection, *, session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_public_chat_messages WHERE session_id=? ORDER BY id LIMIT ? OFFSET ?",
            (session_id, limit, offset),
        ).fetchall()

    def recent_user_topic_keys(
        self, connection: sqlite3.Connection, *, session_id: int, limit: int = 20,
    ) -> list[str]:
        """Bounded lookback for `gap_detector.detect_repeated_question()`
        -- reads only the most recent `limit` user-turn topic keys for
        this session, never a full-table scan."""
        rows = connection.execute(
            """SELECT topic_key FROM mini_brain_public_chat_messages
            WHERE session_id=? AND role='user' AND topic_key IS NOT NULL
            ORDER BY id DESC LIMIT ?""",
            (session_id, limit),
        ).fetchall()
        return [row["topic_key"] for row in rows]

    def session_usage_counts(self, connection: sqlite3.Connection, *, session_id: int) -> dict[str, int]:
        """Aggregated via SQL `SUM()` -- never loads the full message
        history into Python, matching the task spec's own performance
        constraints."""
        row = connection.execute(
            """SELECT COUNT(*) AS message_count, COALESCE(SUM(used_rag), 0) AS used_rag_count,
            COALESCE(SUM(used_vision), 0) AS used_vision_count, COALESCE(SUM(used_tool), 0) AS used_tool_count
            FROM mini_brain_public_chat_messages WHERE session_id=?""",
            (session_id,),
        ).fetchone()
        return dict(row)

    def session_signal_counts_by_type(self, connection: sqlite3.Connection, *, session_id: int) -> dict[str, int]:
        rows = connection.execute(
            "SELECT signal_type, COUNT(*) AS n FROM mini_brain_feedback_signals WHERE session_id=? GROUP BY signal_type",
            (session_id,),
        ).fetchall()
        return {row["signal_type"]: row["n"] for row in rows}

    # -- feedback signals (append-only) ----------------------------------------

    def create_signal(
        self, connection: sqlite3.Connection, *, session_id: int, message_id: int | None, signal_type: str,
        severity: str, normalized_text: str, topic_key: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_feedback_signals(
                public_id, session_id, message_id, signal_type, severity, normalized_text, topic_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (public_id, session_id, message_id, signal_type, severity, normalized_text, topic_key),
        )
        return public_id

    def list_signals(
        self, connection: sqlite3.Connection, *, session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_feedback_signals WHERE session_id=? ORDER BY id LIMIT ? OFFSET ?",
            (session_id, limit, offset),
        ).fetchall()

    def signals_for_clustering(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        """Fetches recent, already-persisted signals across every
        session for `failure_clusterer.py` to group -- bounded by
        pagination rather than an unbounded full-table scan, matching
        the task spec's own performance constraints."""
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_feedback_signals ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- improvement candidates -----------------------------------------------

    def find_candidate_by_topic_key(self, connection: sqlite3.Connection, topic_key: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM mini_brain_improvement_candidates WHERE topic_key=?", (topic_key,)
        ).fetchone()

    def create_candidate(
        self, connection: sqlite3.Connection, *, topic: str, topic_key: str, frequency: int, impact_score: float,
        priority_score: float, recommended_action: str, example_questions: list[str],
        suggested_missing_knowledge: dict[str, Any],
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_improvement_candidates(
                public_id, topic, topic_key, frequency, impact_score, priority_score, recommended_action,
                example_questions_json, suggested_missing_knowledge_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, topic, topic_key, frequency, impact_score, priority_score, recommended_action,
                dumps_json(example_questions), dumps_json(suggested_missing_knowledge),
            ),
        )
        return public_id

    def get_candidate(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_improvement_candidates WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"improvement candidate not found: {public_id}")
        return row

    def list_candidates(
        self, connection: sqlite3.Connection, *, limit: int, offset: int, status: str | None = None,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if status:
            return connection.execute(
                """SELECT * FROM mini_brain_improvement_candidates WHERE status=?
                ORDER BY priority_score DESC LIMIT ? OFFSET ?""",
                (status, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_improvement_candidates ORDER BY priority_score DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def update_candidate(self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any]) -> sqlite3.Row:
        self.get_candidate(connection, public_id)
        json_columns = {f"{f}_json" for f in CANDIDATE_JSON_FIELDS}
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column in json_columns else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_improvement_candidates SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.get_candidate(connection, public_id)

    # -- events (append-only) ---------------------------------------------------

    def create_event(
        self, connection: sqlite3.Connection, *, session_id: int | None = None, candidate_id: int | None = None,
        event_type: str, stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_public_chat_events(
                public_id, session_id, candidate_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (public_id, session_id, candidate_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, session_id: int | None = None, candidate_id: int | None = None,
        limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if session_id is not None:
            return connection.execute(
                """SELECT * FROM mini_brain_public_chat_events WHERE session_id=?
                ORDER BY id DESC LIMIT ? OFFSET ?""",
                (session_id, limit, offset),
            ).fetchall()
        if candidate_id is not None:
            return connection.execute(
                """SELECT * FROM mini_brain_public_chat_events WHERE candidate_id=?
                ORDER BY id DESC LIMIT ? OFFSET ?""",
                (candidate_id, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_public_chat_events ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- analytics ----------------------------------------------------------------

    def analytics_summary(self, connection: sqlite3.Connection) -> dict[str, Any]:
        total_sessions = connection.execute(
            "SELECT COUNT(*) AS n FROM mini_brain_public_chat_sessions"
        ).fetchone()["n"]
        total_messages = connection.execute(
            "SELECT COUNT(*) AS n FROM mini_brain_public_chat_messages"
        ).fetchone()["n"]
        signal_rows = connection.execute(
            "SELECT signal_type, COUNT(*) AS n FROM mini_brain_feedback_signals GROUP BY signal_type"
        ).fetchall()
        return {
            "total_sessions": total_sessions, "total_messages": total_messages,
            "total_signals_by_type": {row["signal_type"]: row["n"] for row in signal_rows},
        }


__all__ = [
    "MiniBrainPublicChatRuntimeRepository", "public_session_row", "public_message_row", "public_signal_row",
    "public_candidate_row", "CANDIDATE_JSON_FIELDS",
]
