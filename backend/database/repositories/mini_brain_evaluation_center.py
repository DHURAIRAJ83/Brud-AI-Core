"""Repository for MB-19: Brud Mini Brain Evaluation & Benchmark
Center.

Four tables, all MB-19's own: `mini_brain_evaluation_sessions`,
`mini_brain_benchmark_results` (one row per individual benchmark
metric), `mini_brain_evaluation_events` (append-only), and
`mini_brain_evaluation_memory` (permanent, insert-only). MB-19 never
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
    "dataset_collection_report", "rag_collection_report", "package_collection_report",
    "language_benchmark_report", "ocr_benchmark_report", "grounding_benchmark_report",
    "retrieval_benchmark_report", "multimodal_benchmark_report", "package_benchmark_report",
    "regression_report", "benchmark_suite", "evaluation_report", "release_readiness",
    "export_manifest",
)
SESSION_LIST_JSON_FIELDS = (
    "source_dataset_public_ids", "source_rag_session_public_ids", "source_training_package_public_ids",
)
_RESULT_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("evaluation session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_result_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("benchmark result row not found")
    data = dict(row)
    for key in list(data):
        if key in _RESULT_INTERNAL or key == "evaluation_session_id":
            data.pop(key)
        elif key == "details_json":
            data["details"] = loads_json(data.pop(key))
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("evaluation memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL or key == "evaluation_session_id":
            data.pop(key)
    return data


class MiniBrainEvaluationCenterRepository(BaseRepository):
    # -- sessions ---------------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, topic: str, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_evaluation_sessions(public_id, topic, created_by_admin_public_id)
            VALUES (?, ?, ?)""",
            (public_id, topic, created_by_admin_public_id),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_evaluation_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"evaluation session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_evaluation_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
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
            f'UPDATE mini_brain_evaluation_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    # -- benchmark results ------------------------------------------------------

    def create_result(
        self, connection: sqlite3.Connection, *, evaluation_session_id: int, category: str,
        metric_name: str, metric_value: float | None, metric_status: str | None,
        details: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_benchmark_results(
                public_id, evaluation_session_id, category, metric_name, metric_value, metric_status,
                details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, evaluation_session_id, category, metric_name, metric_value, metric_status,
                dumps_json(details or {}),
            ),
        )
        return public_id

    def list_results(
        self, connection: sqlite3.Connection, *, evaluation_session_id: int, category: str | None = None,
    ) -> list[sqlite3.Row]:
        query = "SELECT * FROM mini_brain_benchmark_results WHERE evaluation_session_id=?"
        params: list[Any] = [evaluation_session_id]
        if category:
            query += " AND category=?"
            params.append(category)
        query += " ORDER BY id"
        return connection.execute(query, params).fetchall()

    # -- evaluation memory (permanent, insert-only) ------------------------------

    def record_memory(
        self, connection: sqlite3.Connection, *, evaluation_session_id: int, topic: str,
        source_dataset_count: int, source_rag_session_count: int, source_training_package_count: int,
        overall_score: float | None, release_readiness_status: str | None, admin_decision: str,
        recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_evaluation_memory(
                public_id, evaluation_session_id, topic, source_dataset_count, source_rag_session_count,
                source_training_package_count, overall_score, release_readiness_status, admin_decision,
                recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, evaluation_session_id, topic, source_dataset_count, source_rag_session_count,
                source_training_package_count, overall_score, release_readiness_status, admin_decision,
                recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_memory(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_evaluation_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- events (append-only) -----------------------------------------------------

    def record_event(
        self, connection: sqlite3.Connection, *, evaluation_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_evaluation_events(
                public_id, evaluation_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, evaluation_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, evaluation_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_evaluation_events WHERE evaluation_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (evaluation_session_id, limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainEvaluationCenterRepository", "public_session_row", "public_result_row",
    "public_memory_row", "SESSION_JSON_FIELDS", "SESSION_LIST_JSON_FIELDS",
]
