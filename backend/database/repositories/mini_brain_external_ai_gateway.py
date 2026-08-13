"""Repository for MB-21: Brud Mini Brain External AI Evaluation
Gateway.

Four tables, all MB-21's own: `mini_brain_external_ai_sessions`,
`mini_brain_external_ai_provider_runs` (one row per provider call --
only a hash of the raw response is stored by default), `mini_brain_
external_ai_events` (append-only), and `mini_brain_external_ai_memory`
(permanent, insert-only). MB-21 never writes to any other system's
tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
SESSION_JSON_FIELDS = (
    "authorization_report", "sanitization_report", "provider_selection_report", "dispatch_report",
    "collection_report", "normalization_report", "agreement_report", "evidence_bundle",
    "gateway_report",
)
SESSION_LIST_JSON_FIELDS = ("source_dataset_public_ids", "requested_provider_keys")
_PROVIDER_RUN_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("external AI session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_provider_run_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("provider run row not found")
    data = dict(row)
    for key in list(data):
        if key in _PROVIDER_RUN_INTERNAL or key == "external_ai_session_id":
            data.pop(key)
        elif key == "normalized_response_json":
            data["normalized_response"] = loads_json(data.pop(key))
        elif key == "raw_response_retained":
            data[key] = bool(data[key])
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("external AI memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL or key == "external_ai_session_id":
            data.pop(key)
    return data


class MiniBrainExternalAiGatewayRepository(BaseRepository):
    # -- sessions ---------------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, topic: str, purpose: str, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_external_ai_sessions(public_id, topic, purpose, created_by_admin_public_id)
            VALUES (?, ?, ?, ?)""",
            (public_id, topic, purpose, created_by_admin_public_id),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_external_ai_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"external AI session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_external_ai_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def update_session(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any],
    ) -> sqlite3.Row:
        self.session(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        json_columns = {f"{f}_json" for f in SESSION_JSON_FIELDS} | {
            f"{f}_json" for f in SESSION_LIST_JSON_FIELDS
        }
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column in json_columns else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_external_ai_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    # -- provider runs ------------------------------------------------------------

    def create_provider_run(
        self, connection: sqlite3.Connection, *, external_ai_session_id: int, provider_key: str,
        status: str, request_hash: str | None, response_hash: str | None, raw_response_retained: bool,
        normalized_response: dict[str, Any] | None, latency_ms: float | None, error_message: str | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_external_ai_provider_runs(
                public_id, external_ai_session_id, provider_key, status, request_hash, response_hash,
                raw_response_retained, normalized_response_json, latency_ms, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, external_ai_session_id, provider_key, status, request_hash, response_hash,
                int(raw_response_retained), dumps_json(normalized_response or {}), latency_ms, error_message,
            ),
        )
        return public_id

    def list_provider_runs(
        self, connection: sqlite3.Connection, *, external_ai_session_id: int,
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM mini_brain_external_ai_provider_runs WHERE external_ai_session_id=? ORDER BY id",
            (external_ai_session_id,),
        ).fetchall()

    # -- external AI memory (permanent, insert-only) -------------------------------

    def record_memory(
        self, connection: sqlite3.Connection, *, external_ai_session_id: int, topic: str, purpose: str,
        provider_count: int, successful_provider_count: int, agreement_score: float | None,
        admin_decision: str, recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_external_ai_memory(
                public_id, external_ai_session_id, topic, purpose, provider_count,
                successful_provider_count, agreement_score, admin_decision, recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, external_ai_session_id, topic, purpose, provider_count,
                successful_provider_count, agreement_score, admin_decision, recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_memory(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_external_ai_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- events (append-only) -----------------------------------------------------

    def record_event(
        self, connection: sqlite3.Connection, *, external_ai_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_external_ai_events(
                public_id, external_ai_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, external_ai_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, external_ai_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_external_ai_events WHERE external_ai_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (external_ai_session_id, limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainExternalAiGatewayRepository", "public_session_row", "public_provider_run_row",
    "public_memory_row", "SESSION_JSON_FIELDS", "SESSION_LIST_JSON_FIELDS",
]
