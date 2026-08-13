"""Repository for MB-18: Brud Mini Brain Multimodal Training Pipeline
Center.

Four tables, all MB-18's own: `mini_brain_training_pipeline_sessions`,
`mini_brain_training_packages` (one row per generated artifact file --
the real file lives on disk, only its checksum and size are stored
here), `mini_brain_training_pipeline_events` (append-only), and
`mini_brain_training_pipeline_memory` (permanent, insert-only). MB-18
never writes to any other system's tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
SESSION_JSON_FIELDS = (
    "dataset_collection_report", "rag_memory_collection_report", "language_distribution_report",
    "image_statistics_report", "grounding_quality_report", "tokenizer_coverage_report", "splits_report",
    "curriculum_report", "hardware_estimate_report", "package_manifest", "readiness_report",
)
SESSION_LIST_JSON_FIELDS = ("source_dataset_public_ids", "source_rag_memory_public_ids")
_PACKAGE_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("training pipeline session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_package_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("training package row not found")
    data = dict(row)
    for key in list(data):
        if key in _PACKAGE_INTERNAL or key == "training_pipeline_session_id":
            data.pop(key)
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("training pipeline memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL or key == "training_pipeline_session_id":
            data.pop(key)
    return data


class MiniBrainTrainingPipelineRepository(BaseRepository):
    # -- sessions ---------------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, topic: str, source_dataset_public_ids: list[str],
        source_rag_memory_public_ids: list[str], created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_training_pipeline_sessions(
                public_id, topic, source_dataset_public_ids_json, source_rag_memory_public_ids_json,
                created_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?)""",
            (
                public_id, topic, dumps_json(source_dataset_public_ids),
                dumps_json(source_rag_memory_public_ids), created_by_admin_public_id,
            ),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_training_pipeline_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"training pipeline session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_training_pipeline_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
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
            f'UPDATE mini_brain_training_pipeline_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    # -- packages (artifact metadata) -----------------------------------------------

    def create_package(
        self, connection: sqlite3.Connection, *, training_pipeline_session_id: int, artifact_name: str,
        relative_path: str, sha256: str, file_size_bytes: int,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_training_packages(
                public_id, training_pipeline_session_id, artifact_name, relative_path, sha256,
                file_size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, training_pipeline_session_id, artifact_name, relative_path, sha256, file_size_bytes),
        )
        return public_id

    def list_packages(
        self, connection: sqlite3.Connection, *, training_pipeline_session_id: int,
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM mini_brain_training_packages WHERE training_pipeline_session_id=? ORDER BY id",
            (training_pipeline_session_id,),
        ).fetchall()

    def get_package(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_training_packages WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"training package not found: {public_id}")
        return row

    # -- pipeline memory (permanent, insert-only) ------------------------------------

    def record_memory(
        self, connection: sqlite3.Connection, *, training_pipeline_session_id: int, topic: str,
        source_dataset_count: int, source_rag_memory_count: int, package_manifest_checksum: str | None,
        readiness_score: float | None, admin_decision: str, recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_training_pipeline_memory(
                public_id, training_pipeline_session_id, topic, source_dataset_count,
                source_rag_memory_count, package_manifest_checksum, readiness_score, admin_decision,
                recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, training_pipeline_session_id, topic, source_dataset_count,
                source_rag_memory_count, package_manifest_checksum, readiness_score, admin_decision,
                recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_memory(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_training_pipeline_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- events (append-only) -----------------------------------------------------

    def record_event(
        self, connection: sqlite3.Connection, *, training_pipeline_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_training_pipeline_events(
                public_id, training_pipeline_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, training_pipeline_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, training_pipeline_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_training_pipeline_events WHERE training_pipeline_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (training_pipeline_session_id, limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainTrainingPipelineRepository", "public_session_row", "public_package_row",
    "public_memory_row", "SESSION_JSON_FIELDS", "SESSION_LIST_JSON_FIELDS",
]
