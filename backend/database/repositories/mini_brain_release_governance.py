"""Repository for MB-20: Brud Mini Brain Release Readiness & Deployment
Governance Center.

Four tables, all MB-20's own: `mini_brain_release_governance_sessions`,
`mini_brain_release_governance_artifacts` (one row per generated release artifact
file), `mini_brain_release_governance_events` (append-only), and
`mini_brain_release_governance_memory` (permanent, insert-only). MB-20 never
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
    "dataset_collection_report", "rag_collection_report", "training_package_collection_report",
    "evaluation_collection_report", "safety_gate_report", "compliance_gate_report",
    "benchmark_gate_report", "risk_rollback_report", "release_manifest", "release_decision",
    "readiness_report",
)
SESSION_LIST_JSON_FIELDS = ("source_dataset_public_ids", "source_rag_session_public_ids")
_ARTIFACT_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("release session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_artifact_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("release artifact row not found")
    data = dict(row)
    for key in list(data):
        if key in _ARTIFACT_INTERNAL or key == "release_session_id":
            data.pop(key)
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("release memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL or key == "release_session_id":
            data.pop(key)
    return data


class MiniBrainReleaseGovernanceRepository(BaseRepository):
    # -- sessions ---------------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, topic: str, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_release_governance_sessions(public_id, topic, created_by_admin_public_id)
            VALUES (?, ?, ?)""",
            (public_id, topic, created_by_admin_public_id),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_release_governance_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"release session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_release_governance_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
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
            f'UPDATE mini_brain_release_governance_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    # -- artifacts (release package metadata) -----------------------------------

    def create_artifact(
        self, connection: sqlite3.Connection, *, release_session_id: int, artifact_name: str,
        relative_path: str, sha256: str, file_size_bytes: int,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_release_governance_artifacts(
                public_id, release_session_id, artifact_name, relative_path, sha256, file_size_bytes
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, release_session_id, artifact_name, relative_path, sha256, file_size_bytes),
        )
        return public_id

    def list_artifacts(
        self, connection: sqlite3.Connection, *, release_session_id: int,
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM mini_brain_release_governance_artifacts WHERE release_session_id=? ORDER BY id",
            (release_session_id,),
        ).fetchall()

    def get_artifact(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_release_governance_artifacts WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"release artifact not found: {public_id}")
        return row

    # -- release memory (permanent, insert-only) ---------------------------------

    def record_memory(
        self, connection: sqlite3.Connection, *, release_session_id: int, topic: str,
        source_dataset_count: int, source_rag_session_count: int, overall_readiness_score: float | None,
        release_decision_status: str | None, admin_decision: str, recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_release_governance_memory(
                public_id, release_session_id, topic, source_dataset_count, source_rag_session_count,
                overall_readiness_score, release_decision_status, admin_decision,
                recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, release_session_id, topic, source_dataset_count, source_rag_session_count,
                overall_readiness_score, release_decision_status, admin_decision,
                recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_memory(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_release_governance_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- events (append-only) -----------------------------------------------------

    def record_event(
        self, connection: sqlite3.Connection, *, release_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_release_governance_events(
                public_id, release_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, release_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, release_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_release_governance_events WHERE release_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (release_session_id, limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainReleaseGovernanceRepository", "public_session_row", "public_artifact_row",
    "public_memory_row", "SESSION_JSON_FIELDS", "SESSION_LIST_JSON_FIELDS",
]
