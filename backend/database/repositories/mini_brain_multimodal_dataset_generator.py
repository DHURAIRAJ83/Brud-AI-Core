"""Repository for MB-16: Brud Mini Brain Multimodal Dataset Generator
Center.

Four tables, all MB-16's own: `mini_brain_multimodal_dataset_sessions`,
`mini_brain_multimodal_dataset_records` (one row per generated draft
record -- never a Dataset Studio row), `mini_brain_multimodal_dataset_
memory` (permanent, insert-only Dataset Memory), and
`mini_brain_multimodal_dataset_events` (append-only). MB-16 never
writes to any other system's tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
SESSION_JSON_FIELDS = (
    "source_report", "text_section", "image_section", "metadata_report", "conversation_report",
    "instruction_report", "dataset_draft_report", "quality_report", "duplicate_report", "dataset_report",
)
_RECORD_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("multimodal dataset session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_record_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("multimodal dataset record row not found")
    data = dict(row)
    for key in list(data):
        if key in _RECORD_INTERNAL or key == "multimodal_dataset_session_id":
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    data["verified"] = bool(data["verified"])
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("multimodal dataset memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL or key == "multimodal_dataset_session_id":
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class MiniBrainMultimodalDatasetGeneratorRepository(BaseRepository):
    # -- sessions ---------------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, document_source_public_id: str,
        dataset_source_public_id: str | None, language_session_public_id: str | None,
        vision_session_public_id: str | None, vision_model_session_public_id: str | None,
        parent_session_public_id: str | None, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_multimodal_dataset_sessions(
                public_id, document_source_public_id, dataset_source_public_id,
                language_session_public_id, vision_session_public_id,
                vision_model_session_public_id, parent_session_public_id, created_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, document_source_public_id, dataset_source_public_id,
                language_session_public_id, vision_session_public_id, vision_model_session_public_id,
                parent_session_public_id, created_by_admin_public_id,
            ),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_multimodal_dataset_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"multimodal dataset session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_multimodal_dataset_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def update_session(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any],
    ) -> sqlite3.Row:
        self.session(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        json_columns = {f"{f}_json" for f in SESSION_JSON_FIELDS}
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column in json_columns else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_multimodal_dataset_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    # -- records ------------------------------------------------------------------

    def create_record(
        self, connection: sqlite3.Connection, *, multimodal_dataset_session_id: int, record_type: str,
        content: dict[str, Any], record_checksum: str, verified: bool = False, status: str = "active",
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_multimodal_dataset_records(
                public_id, multimodal_dataset_session_id, record_type, content_json, record_checksum,
                verified, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, multimodal_dataset_session_id, record_type, dumps_json(content),
                record_checksum, int(verified), status,
            ),
        )
        return public_id

    def update_record(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any],
    ) -> sqlite3.Row:
        self.get_record(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column == "content_json" else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_multimodal_dataset_records SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.get_record(connection, public_id)

    def get_record(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_multimodal_dataset_records WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"multimodal dataset record not found: {public_id}")
        return row

    def list_records(
        self, connection: sqlite3.Connection, *, multimodal_dataset_session_id: int,
        record_type: str | None = None, status: str | None = None,
    ) -> list[sqlite3.Row]:
        query = "SELECT * FROM mini_brain_multimodal_dataset_records WHERE multimodal_dataset_session_id=?"
        params: list[Any] = [multimodal_dataset_session_id]
        if record_type:
            query += " AND record_type=?"
            params.append(record_type)
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY id"
        return connection.execute(query, params).fetchall()

    # -- dataset memory (permanent, insert-only) -----------------------------------

    def record_memory(
        self, connection: sqlite3.Connection, *, multimodal_dataset_session_id: int, dataset_version: int,
        generated_at: str, source_document_public_id: str, source_dataset_public_id: str | None,
        source_language_session_public_id: str | None, source_vision_session_public_id: str | None,
        source_vision_model_session_public_id: str | None, total_records: int,
        correction_history: list[dict[str, Any]], learning_memory: list[dict[str, Any]],
        provider_information: dict[str, Any], admin_decision: str | None,
        recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_multimodal_dataset_memory(
                public_id, multimodal_dataset_session_id, dataset_version, generated_at,
                source_document_public_id, source_dataset_public_id,
                source_language_session_public_id, source_vision_session_public_id,
                source_vision_model_session_public_id, total_records, correction_history_json,
                learning_memory_json, provider_information_json, admin_decision,
                recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, multimodal_dataset_session_id, dataset_version, generated_at,
                source_document_public_id, source_dataset_public_id,
                source_language_session_public_id, source_vision_session_public_id,
                source_vision_model_session_public_id, total_records, dumps_json(correction_history),
                dumps_json(learning_memory), dumps_json(provider_information), admin_decision,
                recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_memory(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_multimodal_dataset_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- events (append-only) -----------------------------------------------------

    def record_event(
        self, connection: sqlite3.Connection, *, multimodal_dataset_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_multimodal_dataset_events(
                public_id, multimodal_dataset_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, multimodal_dataset_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, multimodal_dataset_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_multimodal_dataset_events WHERE multimodal_dataset_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (multimodal_dataset_session_id, limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainMultimodalDatasetGeneratorRepository", "public_session_row", "public_record_row",
    "public_memory_row", "SESSION_JSON_FIELDS",
]
