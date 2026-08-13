"""Repository for MB-17: Brud Mini Brain Vision RAG & Multimodal
Retrieval Center.

Four tables, all MB-17's own: `mini_brain_vision_rag_sessions`,
`mini_brain_vision_rag_evidence` (one row per retrieved evidence item
-- the structural backbone of "every retrieval result must remain
evidence-linked"), `mini_brain_vision_rag_memory` (permanent, insert-
only), and `mini_brain_vision_rag_events` (append-only). MB-17 never
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
    "text_retrieval_report", "ocr_retrieval_report", "image_retrieval_report",
    "object_retrieval_report", "knowledge_graph_retrieval_report", "evidence_fusion_report",
    "answer_report", "quality_report", "hallucination_report", "rag_report",
)
_EVIDENCE_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_session_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision rag session row not found")
    data = dict(row)
    for key in list(data):
        if key in _SESSION_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_evidence_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision rag evidence row not found")
    data = dict(row)
    for key in list(data):
        if key in _EVIDENCE_INTERNAL or key == "vision_rag_session_id":
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    data["used_in_answer"] = bool(data["used_in_answer"])
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("vision rag memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL or key == "vision_rag_session_id":
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    data["hallucination_flag"] = bool(data["hallucination_flag"])
    return data


class MiniBrainVisionRagRepository(BaseRepository):
    # -- sessions ---------------------------------------------------------------

    def create_session(
        self, connection: sqlite3.Connection, *, multimodal_dataset_session_public_id: str,
        document_source_public_id: str, language_session_public_id: str | None,
        vision_session_public_id: str | None, vision_model_session_public_id: str | None,
        query: str, query_language: str | None, created_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_rag_sessions(
                public_id, multimodal_dataset_session_public_id, document_source_public_id,
                language_session_public_id, vision_session_public_id, vision_model_session_public_id,
                query, query_language, created_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, multimodal_dataset_session_public_id, document_source_public_id,
                language_session_public_id, vision_session_public_id, vision_model_session_public_id,
                query, query_language, created_by_admin_public_id,
            ),
        )
        return public_id

    def session(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_vision_rag_sessions WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"vision rag session not found: {public_id}")
        return row

    def list_sessions(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_vision_rag_sessions ORDER BY id DESC LIMIT ? OFFSET ?",
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
            f'UPDATE mini_brain_vision_rag_sessions SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.session(connection, public_id)

    # -- evidence -------------------------------------------------------------------

    def create_evidence(
        self, connection: sqlite3.Connection, *, vision_rag_session_id: int, evidence_type: str,
        source_record_public_id: str | None, document_source_public_id: str | None,
        page_number: int | None, image_public_id: str | None, object_label: str | None,
        bounding_box: dict[str, Any] | None, graph_edge: dict[str, Any] | None, content_snippet: str,
        relevance_score: float, source: str = "ai_retrieved",
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_rag_evidence(
                public_id, vision_rag_session_id, evidence_type, source_record_public_id,
                document_source_public_id, page_number, image_public_id, object_label,
                bounding_box_json, graph_edge_json, content_snippet, relevance_score, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, vision_rag_session_id, evidence_type, source_record_public_id,
                document_source_public_id, page_number, image_public_id, object_label,
                dumps_json(bounding_box) if bounding_box is not None else None,
                dumps_json(graph_edge) if graph_edge is not None else None, content_snippet,
                relevance_score, source,
            ),
        )
        return public_id

    def update_evidence(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any],
    ) -> sqlite3.Row:
        self.get_evidence(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        json_columns = {"bounding_box_json", "graph_edge_json"}
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column in json_columns else value)
        values.append(public_id)
        connection.execute(
            f'UPDATE mini_brain_vision_rag_evidence SET {", ".join(set_clauses)} WHERE public_id=?',
            values,
        )
        return self.get_evidence(connection, public_id)

    def get_evidence(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_vision_rag_evidence WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"vision rag evidence not found: {public_id}")
        return row

    def list_evidence(
        self, connection: sqlite3.Connection, *, vision_rag_session_id: int,
        evidence_type: str | None = None, status: str | None = None,
    ) -> list[sqlite3.Row]:
        query = "SELECT * FROM mini_brain_vision_rag_evidence WHERE vision_rag_session_id=?"
        params: list[Any] = [vision_rag_session_id]
        if evidence_type:
            query += " AND evidence_type=?"
            params.append(evidence_type)
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY id"
        return connection.execute(query, params).fetchall()

    # -- RAG memory (permanent, insert-only) -----------------------------------

    def record_memory(
        self, connection: sqlite3.Connection, *, vision_rag_session_id: int, query: str,
        evidence_summary: dict[str, Any], final_answer: str | None, confidence: float | None,
        admin_decision: str | None, hallucination_flag: bool, correction_history: list[dict[str, Any]],
        retrieval_latency_ms: float | None, recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_rag_memory(
                public_id, vision_rag_session_id, query, evidence_summary_json, final_answer,
                confidence, admin_decision, hallucination_flag, correction_history_json,
                retrieval_latency_ms, recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, vision_rag_session_id, query, dumps_json(evidence_summary), final_answer,
                confidence, admin_decision, int(hallucination_flag), dumps_json(correction_history),
                retrieval_latency_ms, recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_memory(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_vision_rag_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- events (append-only) -----------------------------------------------------

    def record_event(
        self, connection: sqlite3.Connection, *, vision_rag_session_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_vision_rag_events(
                public_id, vision_rag_session_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, vision_rag_session_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, vision_rag_session_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_vision_rag_events WHERE vision_rag_session_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (vision_rag_session_id, limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainVisionRagRepository", "public_session_row", "public_evidence_row", "public_memory_row",
    "SESSION_JSON_FIELDS",
]
