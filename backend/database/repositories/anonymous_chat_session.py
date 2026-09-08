"""Repository for Anonymous Public Chat Sessions (Phase 8).

Manages ephemeral anonymous chat sessions, secure token hashes,
session lifecycle (active, expired, closed), and privacy-preserving
turn zeroing on clear-chat.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.database.repositories.base import BaseRepository, NotFoundError

_INTERNAL_COLS = {"id", "session_token_hash", "client_ip_hash"}


def public_anonymous_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("anonymous chat session not found")
    data = dict(row)
    for col in _INTERNAL_COLS:
        data.pop(col, None)
    return data


class AnonymousChatSessionRepository(BaseRepository):
    def create_session(
        self,
        connection: sqlite3.Connection,
        *,
        public_id: str,
        conversation_session_public_id: str,
        session_token_hash: str,
        client_ip_hash: str,
        expires_at: str,
    ) -> str:
        connection.execute(
            """
            INSERT INTO anonymous_chat_sessions (
                public_id, conversation_session_public_id, session_token_hash,
                client_ip_hash, status, expires_at, created_at, updated_at, last_activity_at
            ) VALUES (?, ?, ?, ?, 'active', ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                public_id,
                conversation_session_public_id,
                session_token_hash,
                client_ip_hash,
                expires_at,
            ),
        )
        return public_id

    def get_by_conversation_id(
        self, connection: sqlite3.Connection, conversation_session_public_id: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM anonymous_chat_sessions WHERE conversation_session_public_id = ?",
            (conversation_session_public_id,),
        ).fetchone()

    def get_by_public_id(
        self, connection: sqlite3.Connection, public_id: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM anonymous_chat_sessions WHERE public_id = ?",
            (public_id,),
        ).fetchone()

    def update_activity(
        self,
        connection: sqlite3.Connection,
        public_id: str,
        *,
        last_activity_at: str,
        expires_at: str,
    ) -> None:
        connection.execute(
            """
            UPDATE anonymous_chat_sessions
            SET last_activity_at = ?, expires_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE public_id = ?
            """,
            (last_activity_at, expires_at, public_id),
        )

    def mark_expired(self, connection: sqlite3.Connection, public_id: str) -> None:
        connection.execute(
            """
            UPDATE anonymous_chat_sessions
            SET status = 'expired', updated_at = CURRENT_TIMESTAMP
            WHERE public_id = ?
            """,
            (public_id,),
        )

    def close_session(
        self, connection: sqlite3.Connection, conversation_session_public_id: str
    ) -> None:
        connection.execute(
            """
            UPDATE anonymous_chat_sessions
            SET status = 'closed', session_token_hash = '', updated_at = CURRENT_TIMESTAMP
            WHERE conversation_session_public_id = ?
            """,
            (conversation_session_public_id,),
        )
        connection.execute(
            """
            UPDATE conversation_sessions
            SET status = 'closed', closed_at = CURRENT_TIMESTAMP
            WHERE public_id = ?
            """,
            (conversation_session_public_id,),
        )

    def get_session_turns(
        self, connection: sqlite3.Connection, conversation_session_public_id: str
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """
            SELECT t.public_id, t.sequence_number, t.role, t.stored_content,
                   t.language_category, t.token_count, t.created_at
            FROM conversation_turns t
            JOIN conversation_sessions s ON s.id = t.session_id
            WHERE s.public_id = ? AND t.stored_content IS NOT NULL AND t.status = 'accepted'
            ORDER BY t.sequence_number ASC
            """,
            (conversation_session_public_id,),
        ).fetchall()

    def clear_session_content(
        self, connection: sqlite3.Connection, conversation_session_public_id: str
    ) -> None:
        """Zeroes token credentials and closes both session records for privacy, preventing history restoration."""
        self.close_session(connection, conversation_session_public_id)
