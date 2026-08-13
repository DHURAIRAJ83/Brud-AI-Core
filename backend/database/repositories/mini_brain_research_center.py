"""Repository for MB-10: Brud Mini Brain AI Research & Knowledge
Acquisition Center.

Four tables, all MB-10's own: `mini_brain_research_provider_registry`
(real, admin-extensible, seeded with 5 defaults by the migration
itself), `mini_brain_research_memory` (permanent, insert-only),
`mini_brain_research_sessions`, and `mini_brain_research_events`.
MB-10 never writes to any other system's tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

_SESSION_INTERNAL = {"id"}
SESSION_JSON_FIELDS = (
    "research_request", "selected_providers", "local_draft_report", "provider_request",
    "provider_outputs", "consensus_report", "evidence_report", "quality_report",
    "dataset_draft", "rag_report", "training_gate_report", "recommendation_report",
)
_MEMORY_INTERNAL = {"id"}
_MEMORY_JSON_FIELDS = (
    "provider_history", "consensus_report", "dataset_evolution", "training_results",
    "benchmark_results",
)
_PROVIDER_INTERNAL = {"id"}


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("research session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("research memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_provider_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("research provider row not found")
    data = dict(row)
    for key in list(data):
        if key in _PROVIDER_INTERNAL:
            data.pop(key)
    data["requires_external_call"] = bool(data["requires_external_call"])
    return data


class MiniBrainResearchCenterRepository(BaseRepository):
    # -- provider registry ---------------------------------------------------------

    def list_providers(
        self, connection: sqlite3.Connection, *, status: str | None = None,
    ) -> list[sqlite3.Row]:
        if status:
            return connection.execute(
                "SELECT * FROM mini_brain_research_provider_registry WHERE status=? ORDER BY id",
                (status,),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_research_provider_registry ORDER BY id"
        ).fetchall()

    def get_provider(self, connection: sqlite3.Connection, provider_key: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM mini_brain_research_provider_registry WHERE provider_key=?", (provider_key,)
        ).fetchone()

    def add_provider(
        self, connection: sqlite3.Connection, *, provider_key: str, display_name: str,
        requires_external_call: bool, description: str, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_research_provider_registry(
                public_id, provider_key, display_name, requires_external_call, description,
                created_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, provider_key, display_name, int(requires_external_call), description,
             created_by_admin_public_id),
        )
        return public_id

    def set_provider_status(
        self, connection: sqlite3.Connection, provider_key: str, *, status: str,
    ) -> sqlite3.Row:
        connection.execute(
            "UPDATE mini_brain_research_provider_registry SET status=?, updated_at=CURRENT_TIMESTAMP WHERE provider_key=?",
            (status, provider_key),
        )
        row = self.get_provider(connection, provider_key)
        if row is None:
            raise NotFoundError(f"provider not found: {provider_key}")
        return row

    # -- research memory (permanent, insert-only) ------------------------------

    def record_memory(
        self, connection: sqlite3.Connection, *, research_session_public_id: str,
        provider_history: list[dict[str, Any]], consensus_report: dict[str, Any],
        dataset_evolution: dict[str, Any], training_results: dict[str, Any],
        benchmark_results: dict[str, Any], admin_decision: str | None, notes: str,
        recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_research_memory(
                public_id, research_session_public_id, provider_history_json, consensus_report_json,
                dataset_evolution_json, training_results_json, benchmark_results_json,
                admin_decision, notes, recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, research_session_public_id, dumps_json(provider_history),
                dumps_json(consensus_report), dumps_json(dataset_evolution),
                dumps_json(training_results), dumps_json(benchmark_results), admin_decision, notes,
                recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_memory(
        self, connection: sqlite3.Connection, *, limit: int, offset: int
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_research_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def get_memory(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_research_memory WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"research memory entry not found: {public_id}")
        return row

    # -- research sessions ---------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, topic: str, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_research_sessions(
                public_id, topic, created_by_admin_public_id
            ) VALUES (?, ?, ?)""",
            (public_id, topic, created_by_admin_public_id),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_research_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"research session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_research_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
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
            f'UPDATE mini_brain_research_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    def record_event(
        self, connection: sqlite3.Connection, *, research_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_research_events(
                public_id, research_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, research_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, research_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_research_events WHERE research_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (research_session_id, limit, offset),
        ).fetchall()
