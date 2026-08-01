"""Repository for the three Phase 8 Admin Assistant tables added in
migration 029: context snapshots (append-only), tool invocations
(mutable status/result until completion, then delete-blocked), and
feedback (append-only). No raw SQL leaks outside this module."""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json, redact_secrets
from backend.database.repositories.base import BaseRepository, NotFoundError


def _snapshot_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "conversation_session_public_id": row["conversation_session_public_id"],
        "page_id": row["page_id"],
        "tab_id": row["tab_id"],
        "entity_type": row["entity_type"],
        "entity_public_id": row["entity_public_id"],
        "revision_public_id": row["revision_public_id"],
        "sanitized_context": redact_secrets(loads_json(row["sanitized_context_json"] or "{}")),
        "registry_version": row["registry_version"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
    }


def _invocation_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "conversation_session_public_id": row["conversation_session_public_id"],
        "proposal_public_id": row["proposal_public_id"],
        "tool_name": row["tool_name"],
        "mode": row["mode"],
        "input_summary": redact_secrets(loads_json(row["input_summary_json"] or "{}")),
        "result_summary": redact_secrets(loads_json(row["result_summary_json"] or "{}")),
        "status": row["status"],
        "error_code": row["error_code"],
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
    }


def _feedback_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "conversation_session_public_id": row["conversation_session_public_id"],
        "message_reference": row["message_reference"],
        "page_id": row["page_id"],
        "action_id": row["action_id"],
        "rating": row["rating"],
        "comment": row["comment"],
        "registry_version": row["registry_version"],
        "submitted_by_admin_public_id": row["submitted_by_admin_public_id"],
        "created_at": row["created_at"],
    }


class AdminAssistantContextRepository(BaseRepository):
    # -- context snapshots (append-only) --------------------------------

    def create_context_snapshot(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            session_id = self._session_id(connection, values.get("conversation_session_public_id"))
            connection.execute(
                """INSERT INTO admin_assistant_context_snapshots(
                public_id, conversation_session_id, page_id, tab_id, entity_type,
                entity_public_id, revision_public_id, sanitized_context_json,
                registry_version, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    session_id,
                    values["page_id"],
                    values.get("tab_id"),
                    values.get("entity_type"),
                    values.get("entity_public_id"),
                    values.get("revision_public_id"),
                    dumps_json(redact_secrets(values.get("sanitized_context", {}))),
                    values["registry_version"],
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_context_snapshot(public_id)

    def get_context_snapshot(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._snapshot_select_sql() + " WHERE s.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("context snapshot not found")
        return _snapshot_public(row)

    def list_context_snapshots(
        self, *, conversation_session_public_id: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            if conversation_session_public_id:
                rows = connection.execute(
                    self._snapshot_select_sql()
                    + " WHERE cs.public_id=? ORDER BY s.id DESC LIMIT ?",
                    (conversation_session_public_id, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    self._snapshot_select_sql() + " ORDER BY s.id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [_snapshot_public(row) for row in rows]

    @staticmethod
    def _snapshot_select_sql() -> str:
        return (
            "SELECT s.*, cs.public_id AS conversation_session_public_id "
            "FROM admin_assistant_context_snapshots s "
            "LEFT JOIN conversation_sessions cs ON cs.id = s.conversation_session_id"
        )

    # -- tool invocations (mutable until completion, then delete-blocked) --

    def create_tool_invocation(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            session_id = self._session_id(connection, values.get("conversation_session_public_id"))
            connection.execute(
                """INSERT INTO admin_assistant_tool_invocations(
                public_id, conversation_session_id, proposal_public_id, tool_name, mode,
                input_summary_json, performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    public_id,
                    session_id,
                    values.get("proposal_public_id"),
                    values["tool_name"],
                    values["mode"],
                    dumps_json(redact_secrets(values.get("input_summary", {}))),
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_tool_invocation(public_id)

    def complete_tool_invocation(
        self,
        public_id: str,
        *,
        status: str,
        result_summary: dict[str, Any],
        error_code: str | None = None,
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT id FROM admin_assistant_tool_invocations WHERE public_id=?", (public_id,)
            ).fetchone()
            if not current:
                raise NotFoundError("tool invocation not found")
            connection.execute(
                """UPDATE admin_assistant_tool_invocations SET status=?, result_summary_json=?,
                error_code=?, completed_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (status, dumps_json(redact_secrets(result_summary)), error_code, public_id),
            )
        return self.get_tool_invocation(public_id)

    def get_tool_invocation(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._invocation_select_sql() + " WHERE t.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("tool invocation not found")
        return _invocation_public(row)

    def list_tool_invocations(
        self, *, conversation_session_public_id: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            if conversation_session_public_id:
                rows = connection.execute(
                    self._invocation_select_sql()
                    + " WHERE cs.public_id=? ORDER BY t.id DESC LIMIT ?",
                    (conversation_session_public_id, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    self._invocation_select_sql() + " ORDER BY t.id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [_invocation_public(row) for row in rows]

    @staticmethod
    def _invocation_select_sql() -> str:
        return (
            "SELECT t.*, cs.public_id AS conversation_session_public_id "
            "FROM admin_assistant_tool_invocations t "
            "LEFT JOIN conversation_sessions cs ON cs.id = t.conversation_session_id"
        )

    # -- feedback (append-only) ------------------------------------------

    def create_feedback(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            session_id = self._session_id(connection, values.get("conversation_session_public_id"))
            connection.execute(
                """INSERT INTO admin_assistant_feedback(
                public_id, conversation_session_id, message_reference, page_id, action_id,
                rating, comment, registry_version, submitted_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    session_id,
                    values.get("message_reference"),
                    values.get("page_id"),
                    values.get("action_id"),
                    values["rating"],
                    values.get("comment", ""),
                    values["registry_version"],
                    values["submitted_by_admin_public_id"],
                ),
            )
        return self.get_feedback(public_id)

    def get_feedback(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._feedback_select_sql() + " WHERE f.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("feedback not found")
        return _feedback_public(row)

    def list_feedback(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            rows = connection.execute(
                self._feedback_select_sql() + " ORDER BY f.id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_feedback_public(row) for row in rows]

    @staticmethod
    def _feedback_select_sql() -> str:
        return (
            "SELECT f.*, cs.public_id AS conversation_session_public_id "
            "FROM admin_assistant_feedback f "
            "LEFT JOIN conversation_sessions cs ON cs.id = f.conversation_session_id"
        )

    # -- shared -----------------------------------------------------------

    @staticmethod
    def _session_id(connection: sqlite3.Connection, session_public_id: str | None) -> int | None:
        if not session_public_id:
            return None
        row = connection.execute(
            "SELECT id FROM conversation_sessions WHERE public_id=?", (session_public_id,)
        ).fetchone()
        return row["id"] if row else None
