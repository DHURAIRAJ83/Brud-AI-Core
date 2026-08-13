"""Persistence for `public_chat_routing_events` and
`public_chat_feedback_events` (Phase 18, migration 040). Never stores
raw question/answer text -- only SHA-256 hashes and structured
classification/route outputs, mirroring Phase 17's
`routing_classification_decisions` convention exactly. Append-only.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository

_EVENT_COLUMNS = """
    public_id, request_id, input_hash, classification_decision_public_id,
    recommended_route, resolved_route, route_status, evidence_status,
    detected_language, answer_language, safety_status, fallbacks_attempted_json,
    latency_ms, error_code, conversation_id, created_at
"""


def _event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "request_id": row["request_id"],
        "input_hash": row["input_hash"],
        "classification_decision_public_id": row["classification_decision_public_id"],
        "recommended_route": row["recommended_route"],
        "resolved_route": row["resolved_route"],
        "route_status": row["route_status"],
        "evidence_status": row["evidence_status"],
        "detected_language": row["detected_language"],
        "answer_language": row["answer_language"],
        "safety_status": row["safety_status"],
        "fallbacks_attempted": loads_json(row["fallbacks_attempted_json"]),
        "latency_ms": row["latency_ms"],
        "error_code": row["error_code"],
        "conversation_id": row["conversation_id"],
        "created_at": row["created_at"],
    }


def _feedback_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "request_id": row["request_id"],
        "route_used": row["route_used"],
        "answer_hash": row["answer_hash"],
        "feedback_type": row["feedback_type"],
        "comment": row["comment"],
        "created_at": row["created_at"],
    }


class PublicChatRoutingRepository(BaseRepository):
    def record_event(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO public_chat_routing_events(
                    public_id, request_id, input_hash, classification_decision_public_id,
                    recommended_route, resolved_route, route_status, evidence_status,
                    detected_language, answer_language, safety_status,
                    fallbacks_attempted_json, latency_ms, error_code, conversation_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    values["request_id"],
                    values["input_hash"],
                    values.get("classification_decision_public_id"),
                    values["recommended_route"],
                    values["resolved_route"],
                    values["route_status"],
                    values["evidence_status"],
                    values["detected_language"],
                    values.get("answer_language"),
                    values["safety_status"],
                    dumps_json(list(values.get("fallbacks_attempted", ()))),
                    values.get("latency_ms"),
                    values.get("error_code"),
                    values.get("conversation_id"),
                ),
            )
            row = connection.execute(
                f"SELECT {_EVENT_COLUMNS} FROM public_chat_routing_events WHERE public_id = ?",
                (public_id,),
            ).fetchone()
        return _event_public(row)

    def get_event(self, public_id: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                f"SELECT {_EVENT_COLUMNS} FROM public_chat_routing_events WHERE public_id = ?",
                (public_id,),
            ).fetchone()
        return _event_public(row) if row else None

    def list_events(
        self, *, limit: int, offset: int, resolved_route: str | None = None
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clause = "WHERE resolved_route = ?" if resolved_route else ""
        params: tuple[Any, ...] = (resolved_route,) if resolved_route else ()
        with self.transaction() as connection:
            rows = connection.execute(
                f"""SELECT {_EVENT_COLUMNS} FROM public_chat_routing_events
                {clause} ORDER BY id DESC LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            ).fetchall()
        return [_event_public(row) for row in rows]

    def count_resolved_route_for_conversation(
        self, conversation_id: str, resolved_route: str
    ) -> int:
        """Phase 19 Step 15 -- bounded clarification-attempt tracking.
        Reuses this existing, already-append-only table (which already
        stores `conversation_id`) rather than adding a new tracking
        table or storing raw conversation content anywhere."""

        if not conversation_id:
            return 0
        with self.transaction() as connection:
            return connection.execute(
                "SELECT COUNT(*) FROM public_chat_routing_events "
                "WHERE conversation_id = ? AND resolved_route = ?",
                (conversation_id, resolved_route),
            ).fetchone()[0]

    def aggregate_metrics(self) -> dict[str, Any]:
        with self.transaction() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM public_chat_routing_events"
            ).fetchone()[0]
            by_route = connection.execute(
                "SELECT resolved_route, COUNT(*) FROM public_chat_routing_events "
                "GROUP BY resolved_route"
            ).fetchall()
            by_safety = connection.execute(
                "SELECT safety_status, COUNT(*) FROM public_chat_routing_events "
                "GROUP BY safety_status"
            ).fetchall()
            web_unavailable = connection.execute(
                "SELECT COUNT(*) FROM public_chat_routing_events "
                "WHERE recommended_route='trusted_web'"
            ).fetchone()[0]
            tool_unavailable = connection.execute(
                "SELECT COUNT(*) FROM public_chat_routing_events WHERE recommended_route='tool'"
            ).fetchone()[0]
            avg_latency = connection.execute(
                "SELECT AVG(latency_ms) FROM public_chat_routing_events "
                "WHERE latency_ms IS NOT NULL"
            ).fetchone()[0]
            error_count = connection.execute(
                "SELECT COUNT(*) FROM public_chat_routing_events WHERE error_code IS NOT NULL"
            ).fetchone()[0]
        return {
            "total_requests": total,
            "by_resolved_route": {row[0]: row[1] for row in by_route},
            "by_safety_status": {row[0]: row[1] for row in by_safety},
            "trusted_web_unavailable_count": web_unavailable,
            "tool_unavailable_count": tool_unavailable,
            "average_latency_ms": avg_latency,
            "error_count": error_count,
        }

    def language_compliance_summary(self) -> dict[str, Any]:
        with self.transaction() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM public_chat_routing_events WHERE answer_language IS NOT NULL"
            ).fetchone()[0]
            violations = connection.execute(
                "SELECT COUNT(*) FROM public_chat_routing_events "
                "WHERE answer_language NOT IN ('ta','en')"
            ).fetchone()[0]
        return {"total_answered": total, "language_policy_violations": violations}

    def record_feedback(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO public_chat_feedback_events(
                    public_id, request_id, route_used, answer_hash, feedback_type, comment
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    values["request_id"],
                    values["route_used"],
                    values["answer_hash"],
                    values["feedback_type"],
                    values.get("comment"),
                ),
            )
            row = connection.execute(
                """SELECT public_id, request_id, route_used, answer_hash, feedback_type, comment,
                created_at FROM public_chat_feedback_events WHERE public_id = ?""",
                (public_id,),
            ).fetchone()
        return _feedback_public(row)

    def list_feedback_events(
        self, *, limit: int, offset: int, feedback_type: str | None = None
    ) -> list[dict[str, Any]]:
        """MB-08: read-only listing, added because no accessor existed for
        already-stored feedback events -- mirrors `list_events()` exactly,
        adds no table and changes no existing method."""

        limit, offset = self.pagination(limit, offset)
        clause = "WHERE feedback_type = ?" if feedback_type else ""
        params: tuple[Any, ...] = (feedback_type,) if feedback_type else ()
        with self.transaction() as connection:
            rows = connection.execute(
                f"""SELECT public_id, request_id, route_used, answer_hash, feedback_type, comment,
                created_at FROM public_chat_feedback_events
                {clause} ORDER BY id DESC LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            ).fetchall()
        return [_feedback_public(row) for row in rows]


__all__ = ["PublicChatRoutingRepository"]
