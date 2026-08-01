"""Phase 19 persistence for the knowledge-gap registry (migration 041).

`knowledge_gap_cases` and `knowledge_gap_clusters` are the only two
mutable rows in this module -- every other table is append-only,
mirroring `public_chat_routing_events`'s convention exactly. No raw
question/answer text is ever written by this repository; callers pass
already privacy-processed/canonicalized values only.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError


def _case_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "cluster_public_id": row["cluster_public_id"]
        if "cluster_public_id" in row.keys()
        else None,
        "event_type": row["event_type"],
        "primary_reason_code": row["primary_reason_code"],
        "reason_codes": loads_json(row["reason_codes_json"]),
        "status": row["status"],
        "stage": row["stage"],
        "language": row["language"],
        "domain": row["domain"],
        "intent": row["intent"],
        "freshness": row["freshness"],
        "input_hash": row["input_hash"],
        "canonical_question": row["canonical_question"],
        "redacted_question": row["redacted_question"],
        "content_unavailable_for_review": bool(row["content_unavailable_for_review"]),
        "retention_policy": row["retention_policy"],
        "frequency": row["frequency"],
        "priority_score": row["priority_score"],
        "priority_band": row["priority_band"],
        "priority_reason_codes": loads_json(row["priority_reason_codes_json"]),
        "eligible_for_rag_research": bool(row["eligible_for_rag_research"]),
        "eligible_for_rag_trial_proposal": bool(row["eligible_for_rag_trial_proposal"]),
        "rag_handoff_reason_codes": loads_json(row["rag_handoff_reason_codes_json"]),
        "eligible_for_training_assessment": bool(row["eligible_for_training_assessment"]),
        "training_handoff_reason_codes": loads_json(row["training_handoff_reason_codes_json"]),
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


_CASE_COLUMNS = """
    kgc.public_id, kgc.event_type, kgc.primary_reason_code, kgc.reason_codes_json,
    kgc.status, kgc.stage, kgc.language, kgc.domain, kgc.intent, kgc.freshness,
    kgc.input_hash, kgc.canonical_question, kgc.redacted_question,
    kgc.content_unavailable_for_review, kgc.retention_policy, kgc.frequency,
    kgc.priority_score, kgc.priority_band, kgc.priority_reason_codes_json,
    kgc.eligible_for_rag_research, kgc.eligible_for_rag_trial_proposal,
    kgc.rag_handoff_reason_codes_json, kgc.eligible_for_training_assessment,
    kgc.training_handoff_reason_codes_json, kgc.first_seen_at, kgc.last_seen_at,
    kgc.created_at, kgc.updated_at, cl.public_id AS cluster_public_id
"""


def _occurrence_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "routing_event_public_id": row["routing_event_public_id"],
        "feedback_event_public_id": row["feedback_event_public_id"],
        "request_hash": row["request_hash"],
        "route_recommended": row["route_recommended"],
        "route_used": row["route_used"],
        "evidence_status": row["evidence_status"],
        "confidence_band": row["confidence_band"],
        "event_type": row["event_type"],
        "reason_codes": loads_json(row["reason_codes_json"]),
        "language": row["language"],
        "domain": row["domain"],
        "intent": row["intent"],
        "freshness": row["freshness"],
        "privacy_status": row["privacy_status"],
        "occurred_at": row["occurred_at"],
    }


def _cluster_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "canonical_question": row["canonical_question"],
        "primary_language": row["primary_language"],
        "domain": row["domain"],
        "intent": row["intent"],
        "freshness": row["freshness"],
        "cluster_type": row["cluster_type"],
        "frequency": row["frequency"],
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "priority_score": row["priority_score"],
        "priority_band": row["priority_band"],
        "priority_reason_codes": loads_json(row["priority_reason_codes_json"]),
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class KnowledgeGapRepository(BaseRepository):
    # -- cases

    def create_case(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO knowledge_gap_cases(
                    public_id, event_type, primary_reason_code, reason_codes_json, status,
                    stage, language, domain, intent, freshness, input_hash, canonical_question,
                    redacted_question, content_unavailable_for_review, retention_policy
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    values["event_type"],
                    values["primary_reason_code"],
                    dumps_json(list(values.get("reason_codes", ()))),
                    values.get("status", "new"),
                    values.get("stage", "capture"),
                    values.get("language"),
                    values.get("domain"),
                    values.get("intent"),
                    values.get("freshness"),
                    values["input_hash"],
                    values.get("canonical_question"),
                    values.get("redacted_question"),
                    int(values.get("content_unavailable_for_review", False)),
                    values.get("retention_policy", "standard"),
                ),
            )
            row = self._fetch_case(connection, public_id)
        self._record_status_event(
            public_id,
            from_status=None,
            to_status=row["status"],
            from_stage=None,
            to_stage=row["stage"],
            reason="case_created",
            changed_by="system",
        )
        return row

    def _fetch_case(self, connection: sqlite3.Connection, public_id: str) -> dict[str, Any]:
        row = connection.execute(
            f"""SELECT {_CASE_COLUMNS} FROM knowledge_gap_cases kgc
            LEFT JOIN knowledge_gap_clusters cl ON cl.id = kgc.cluster_id
            WHERE kgc.public_id = ?""",
            (public_id,),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"knowledge gap case not found: {public_id}")
        return _case_public(row)

    def get_case(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            return self._fetch_case(connection, public_id)

    def find_case_by_input_hash(self, input_hash: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT public_id FROM knowledge_gap_cases WHERE input_hash = ? "
                "ORDER BY id DESC LIMIT 1",
                (input_hash,),
            ).fetchone()
            if row is None:
                return None
            return self._fetch_case(connection, row["public_id"])

    def list_cases(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
        event_type: str | None = None,
        priority_band: str | None = None,
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses = []
        params: list[Any] = []
        if status:
            clauses.append("kgc.status = ?")
            params.append(status)
        if event_type:
            clauses.append("kgc.event_type = ?")
            params.append(event_type)
        if priority_band:
            clauses.append("kgc.priority_band = ?")
            params.append(priority_band)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                f"""SELECT {_CASE_COLUMNS} FROM knowledge_gap_cases kgc
                LEFT JOIN knowledge_gap_clusters cl ON cl.id = kgc.cluster_id
                {where} ORDER BY kgc.priority_score DESC, kgc.id DESC LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            ).fetchall()
        return [_case_public(row) for row in rows]

    def list_open_capability_gap_candidates(
        self, *, event_type: str, domain: str | None, intent: str | None, freshness: str | None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Phase 20 Step 26 -- bounded candidate set for capability-
        resolution linkage: only `web_capability_gap`/`tool_capability_gap`
        cases still open (not already `resolved`/`rejected`/`blocked`/
        `archived`/`deleted_payload`), matching the just-answered
        request's own `(domain, intent, freshness)` -- the same
        conservative pre-filter `KnowledgeGapClusteringService` already
        uses, applied here before any near-duplicate comparison so the
        comparison set is always small and bounded."""

        terminal_statuses = ("resolved", "rejected", "blocked", "archived", "deleted_payload")
        clauses = [
            "kgc.event_type = ?",
            f"kgc.status NOT IN ({','.join('?' for _ in terminal_statuses)})",
        ]
        params: list[Any] = [event_type, *terminal_statuses]
        if domain is not None:
            clauses.append("kgc.domain = ?")
            params.append(domain)
        if intent is not None:
            clauses.append("kgc.intent = ?")
            params.append(intent)
        if freshness is not None:
            clauses.append("kgc.freshness = ?")
            params.append(freshness)
        where = " AND ".join(clauses)
        with self.transaction() as connection:
            rows = connection.execute(
                f"""SELECT {_CASE_COLUMNS} FROM knowledge_gap_cases kgc
                LEFT JOIN knowledge_gap_clusters cl ON cl.id = kgc.cluster_id
                WHERE {where} ORDER BY kgc.id DESC LIMIT ?""",
                (*params, limit),
            ).fetchall()
        return [_case_public(row) for row in rows]

    def touch_case_occurrence(self, public_id: str) -> dict[str, Any]:
        """Increments frequency and bumps last_seen_at -- called once per
        new occurrence linked to an existing case."""

        with self.transaction() as connection:
            connection.execute(
                """UPDATE knowledge_gap_cases SET frequency = frequency + 1,
                last_seen_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE public_id = ?""",
                (public_id,),
            )
            return self._fetch_case(connection, public_id)

    def update_case_priority(
        self,
        public_id: str,
        *,
        priority_score: float,
        priority_band: str,
        priority_reason_codes: list[str],
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            connection.execute(
                """UPDATE knowledge_gap_cases SET priority_score = ?, priority_band = ?,
                priority_reason_codes_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE public_id = ?""",
                (priority_score, priority_band, dumps_json(priority_reason_codes), public_id),
            )
            return self._fetch_case(connection, public_id)

    def update_case_status_stage(
        self,
        public_id: str,
        *,
        status: str,
        stage: str,
        reason: str,
        changed_by: str,
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            current = self._fetch_case(connection, public_id)
            connection.execute(
                """UPDATE knowledge_gap_cases SET status = ?, stage = ?,
                updated_at = CURRENT_TIMESTAMP WHERE public_id = ?""",
                (status, stage, public_id),
            )
            result = self._fetch_case(connection, public_id)
        self._record_status_event(
            public_id,
            from_status=current["status"],
            to_status=status,
            from_stage=current["stage"],
            to_stage=stage,
            reason=reason,
            changed_by=changed_by,
        )
        return result

    def update_case_handoff_eligibility(
        self,
        public_id: str,
        *,
        rag_research: bool,
        rag_trial: bool,
        rag_reason_codes: list[str],
        training_assessment: bool,
        training_reason_codes: list[str],
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            connection.execute(
                """UPDATE knowledge_gap_cases SET eligible_for_rag_research = ?,
                eligible_for_rag_trial_proposal = ?, rag_handoff_reason_codes_json = ?,
                eligible_for_training_assessment = ?, training_handoff_reason_codes_json = ?,
                updated_at = CURRENT_TIMESTAMP WHERE public_id = ?""",
                (
                    int(rag_research),
                    int(rag_trial),
                    dumps_json(rag_reason_codes),
                    int(training_assessment),
                    dumps_json(training_reason_codes),
                    public_id,
                ),
            )
            return self._fetch_case(connection, public_id)

    def link_case_to_cluster(self, case_public_id: str, cluster_public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            cluster_id = self._cluster_row_id(connection, cluster_public_id)
            connection.execute(
                "UPDATE knowledge_gap_cases SET cluster_id = ?, updated_at = CURRENT_TIMESTAMP "
                "WHERE public_id = ?",
                (cluster_id, case_public_id),
            )
            return self._fetch_case(connection, case_public_id)

    def execute_case_deletion(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            connection.execute(
                """UPDATE knowledge_gap_cases SET redacted_question = NULL,
                canonical_question = NULL, content_unavailable_for_review = 1,
                status = 'deleted_payload', retention_policy = 'not_retained',
                updated_at = CURRENT_TIMESTAMP WHERE public_id = ?""",
                (public_id,),
            )
            return self._fetch_case(connection, public_id)

    # -- occurrences

    def record_occurrence(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = None
            if values.get("case_public_id"):
                case_id = self._case_row_id(connection, values["case_public_id"])
            connection.execute(
                """INSERT INTO knowledge_gap_occurrences(
                    public_id, case_id, routing_event_public_id, feedback_event_public_id,
                    request_hash, route_recommended, route_used, evidence_status,
                    confidence_band, event_type, reason_codes_json, language, domain, intent,
                    freshness, privacy_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    case_id,
                    values.get("routing_event_public_id"),
                    values.get("feedback_event_public_id"),
                    values["request_hash"],
                    values.get("route_recommended"),
                    values.get("route_used"),
                    values.get("evidence_status"),
                    values.get("confidence_band"),
                    values["event_type"],
                    dumps_json(list(values.get("reason_codes", ()))),
                    values.get("language"),
                    values.get("domain"),
                    values.get("intent"),
                    values.get("freshness"),
                    values.get("privacy_status", "standard"),
                ),
            )
            row = connection.execute(
                "SELECT * FROM knowledge_gap_occurrences WHERE public_id = ?", (public_id,)
            ).fetchone()
            case_public_id = values.get("case_public_id")
        result = dict(_occurrence_public(row))
        result["case_public_id"] = case_public_id
        return result

    def list_occurrences_for_case(
        self, case_public_id: str, *, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, case_public_id)
            rows = connection.execute(
                """SELECT * FROM knowledge_gap_occurrences WHERE case_id = ?
                ORDER BY id DESC LIMIT ? OFFSET ?""",
                (case_id, limit, offset),
            ).fetchall()
        results = []
        for row in rows:
            item = _occurrence_public(row)
            item["case_public_id"] = case_public_id
            results.append(item)
        return results

    def count_occurrences_for_case(self, case_public_id: str, *, event_type: str) -> int:
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, case_public_id)
            return connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_occurrences WHERE case_id = ? "
                "AND event_type = ?",
                (case_id, event_type),
            ).fetchone()[0]

    # -- clusters

    def create_cluster(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO knowledge_gap_clusters(
                    public_id, canonical_question, primary_language, domain, intent, freshness,
                    cluster_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    values["canonical_question"],
                    values["primary_language"],
                    values.get("domain"),
                    values.get("intent"),
                    values.get("freshness"),
                    values.get("cluster_type", "knowledge_gap"),
                ),
            )
            return self._fetch_cluster(connection, public_id)

    def _fetch_cluster(self, connection: sqlite3.Connection, public_id: str) -> dict[str, Any]:
        row = connection.execute(
            "SELECT * FROM knowledge_gap_clusters WHERE public_id = ?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"knowledge gap cluster not found: {public_id}")
        return _cluster_public(row)

    def get_cluster(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            return self._fetch_cluster(connection, public_id)

    def list_clusters(self, *, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_gap_clusters ORDER BY priority_score DESC, id DESC "
                "LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_cluster_public(row) for row in rows]

    def recalculate_cluster_frequency(self, cluster_public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            cluster_id = self._cluster_row_id(connection, cluster_public_id)
            total_frequency = connection.execute(
                "SELECT COALESCE(SUM(frequency), 0) FROM knowledge_gap_cases WHERE cluster_id = ?",
                (cluster_id,),
            ).fetchone()[0]
            connection.execute(
                """UPDATE knowledge_gap_clusters SET frequency = ?, last_seen_at =
                CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE public_id = ?""",
                (total_frequency, cluster_public_id),
            )
            return self._fetch_cluster(connection, cluster_public_id)

    def update_cluster_priority(
        self,
        public_id: str,
        *,
        priority_score: float,
        priority_band: str,
        priority_reason_codes: list[str],
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            connection.execute(
                """UPDATE knowledge_gap_clusters SET priority_score = ?, priority_band = ?,
                priority_reason_codes_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE public_id = ?""",
                (priority_score, priority_band, dumps_json(priority_reason_codes), public_id),
            )
            return self._fetch_cluster(connection, public_id)

    def add_cluster_member(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            cluster_id = self._cluster_row_id(connection, values["cluster_public_id"])
            case_id = self._case_row_id(connection, values["case_public_id"])
            connection.execute(
                """INSERT INTO knowledge_gap_cluster_members(
                    public_id, cluster_id, case_id, member_status, decision,
                    confirmed_by_admin_public_id
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    cluster_id,
                    case_id,
                    values.get("member_status", "active"),
                    values["decision"],
                    values.get("confirmed_by_admin_public_id"),
                ),
            )
            connection.execute(
                "UPDATE knowledge_gap_cases SET cluster_id = ? WHERE public_id = ?",
                (cluster_id, values["case_public_id"]),
            )
        return {
            "public_id": public_id,
            "cluster_public_id": values["cluster_public_id"],
            "case_public_id": values["case_public_id"],
            "decision": values["decision"],
        }

    def list_cluster_members(self, cluster_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            cluster_id = self._cluster_row_id(connection, cluster_public_id)
            rows = connection.execute(
                """SELECT m.public_id, m.member_status, m.decision, m.created_at,
                c.public_id AS case_public_id FROM knowledge_gap_cluster_members m
                JOIN knowledge_gap_cases c ON c.id = m.case_id
                WHERE m.cluster_id = ? ORDER BY m.id DESC""",
                (cluster_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- reviews

    def record_review(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, values["case_public_id"])
            connection.execute(
                """INSERT INTO knowledge_gap_reviews(
                    public_id, case_id, decision, comment, reviewed_by_admin_public_id,
                    stale_check_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    case_id,
                    values["decision"],
                    values.get("comment"),
                    values["reviewed_by_admin_public_id"],
                    values.get("stale_check_fingerprint"),
                ),
            )
        return {
            "public_id": public_id,
            "case_public_id": values["case_public_id"],
            "decision": values["decision"],
        }

    def list_reviews_for_case(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, case_public_id)
            rows = connection.execute(
                "SELECT * FROM knowledge_gap_reviews WHERE case_id = ? ORDER BY id DESC",
                (case_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- research notes

    def record_research_note(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, values["case_public_id"])
            connection.execute(
                """INSERT INTO knowledge_gap_research_notes(
                    public_id, case_id, note_type, note_text_redacted, source_reference,
                    author_admin_id
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    case_id,
                    values["note_type"],
                    values["note_text_redacted"],
                    values.get("source_reference"),
                    values["author_admin_id"],
                ),
            )
        return {"public_id": public_id, "case_public_id": values["case_public_id"]}

    def list_notes_for_case(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, case_public_id)
            rows = connection.execute(
                "SELECT * FROM knowledge_gap_research_notes WHERE case_id = ? ORDER BY id DESC",
                (case_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- resolution

    def record_resolution(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, values["case_public_id"])
            connection.execute(
                """INSERT INTO knowledge_gap_resolution_events(
                    public_id, case_id, resolution_type, notes, resolved_by_admin_public_id
                ) VALUES (?, ?, ?, ?, ?)""",
                (
                    public_id,
                    case_id,
                    values["resolution_type"],
                    values.get("notes"),
                    values["resolved_by_admin_public_id"],
                ),
            )
        return {
            "public_id": public_id,
            "case_public_id": values["case_public_id"],
            "resolution_type": values["resolution_type"],
        }

    def list_resolutions_for_case(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, case_public_id)
            rows = connection.execute(
                "SELECT * FROM knowledge_gap_resolution_events WHERE case_id = ? ORDER BY id DESC",
                (case_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- status events

    def _record_status_event(
        self,
        case_public_id: str,
        *,
        from_status: str | None,
        to_status: str,
        from_stage: str | None,
        to_stage: str,
        reason: str,
        changed_by: str,
    ) -> None:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, case_public_id)
            connection.execute(
                """INSERT INTO knowledge_gap_status_events(
                    public_id, case_id, from_status, to_status, from_stage, to_stage, reason,
                    changed_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    case_id,
                    from_status,
                    to_status,
                    from_stage,
                    to_stage,
                    reason,
                    changed_by,
                ),
            )

    def list_status_events_for_case(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, case_public_id)
            rows = connection.execute(
                "SELECT * FROM knowledge_gap_status_events WHERE case_id = ? ORDER BY id DESC",
                (case_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    # -- deletion

    def request_deletion(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, values["case_public_id"])
            connection.execute(
                """INSERT INTO knowledge_gap_deletion_requests(
                    public_id, case_id, state, requested_by_admin_public_id, reason
                ) VALUES (?, ?, 'requested', ?, ?)""",
                (public_id, case_id, values["requested_by_admin_public_id"], values.get("reason")),
            )
        return {
            "public_id": public_id,
            "case_public_id": values["case_public_id"],
            "state": "requested",
        }

    def advance_deletion_state(
        self,
        case_public_id: str,
        *,
        state: str,
        admin_public_id: str,
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, case_public_id)
            latest = connection.execute(
                """SELECT requested_by_admin_public_id, reason FROM knowledge_gap_deletion_requests
                WHERE case_id = ? ORDER BY id DESC LIMIT 1""",
                (case_id,),
            ).fetchone()
            if latest is None:
                raise NotFoundError(f"no deletion request found for case: {case_public_id}")
            connection.execute(
                """INSERT INTO knowledge_gap_deletion_requests(
                    public_id, case_id, state, requested_by_admin_public_id,
                    confirmed_by_admin_public_id, reason
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    case_id,
                    state,
                    latest["requested_by_admin_public_id"],
                    admin_public_id,
                    latest["reason"],
                ),
            )
        return {"public_id": public_id, "case_public_id": case_public_id, "state": state}

    def list_deletion_requests_for_case(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, case_public_id)
            rows = connection.execute(
                "SELECT * FROM knowledge_gap_deletion_requests WHERE case_id = ? ORDER BY id DESC",
                (case_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def latest_deletion_state(self, case_public_id: str) -> str | None:
        with self.transaction() as connection:
            case_id = self._case_row_id(connection, case_public_id)
            row = connection.execute(
                "SELECT state FROM knowledge_gap_deletion_requests WHERE case_id = ? "
                "ORDER BY id DESC LIMIT 1",
                (case_id,),
            ).fetchone()
        return row["state"] if row else None

    # -- daily reports

    def record_daily_report(self, report_date: str, summary: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO knowledge_gap_daily_reports(public_id, report_date, summary_json)
                VALUES (?, ?, ?)""",
                (public_id, report_date, dumps_json(summary)),
            )
        return {"public_id": public_id, "report_date": report_date, "summary": summary}

    def get_latest_daily_report(self) -> dict[str, Any] | None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_gap_daily_reports ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return {
            "public_id": row["public_id"],
            "report_date": row["report_date"],
            "summary": loads_json(row["summary_json"]),
            "created_at": row["created_at"],
        }

    def list_daily_reports(self, *, limit: int = 30) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_gap_daily_reports ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [
            {
                "public_id": row["public_id"],
                "report_date": row["report_date"],
                "summary": loads_json(row["summary_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    # -- aggregate overview / summaries

    def aggregate_overview(self) -> dict[str, Any]:
        with self.transaction() as connection:
            total_cases = connection.execute("SELECT COUNT(*) FROM knowledge_gap_cases").fetchone()[
                0
            ]
            by_event_type = connection.execute(
                "SELECT event_type, COUNT(*) FROM knowledge_gap_cases GROUP BY event_type"
            ).fetchall()
            by_status = connection.execute(
                "SELECT status, COUNT(*) FROM knowledge_gap_cases GROUP BY status"
            ).fetchall()
            by_priority_band = connection.execute(
                "SELECT priority_band, COUNT(*) FROM knowledge_gap_cases GROUP BY priority_band"
            ).fetchall()
            awaiting_review = connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_cases WHERE status = 'review_required'"
            ).fetchone()[0]
            eligible_rag = connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_cases WHERE eligible_for_rag_research = 1"
            ).fetchone()[0]
            eligible_training = connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_cases "
                "WHERE eligible_for_training_assessment = 1"
            ).fetchone()[0]
        return {
            "total_cases": total_cases,
            "by_event_type": {row[0]: row[1] for row in by_event_type},
            "by_status": {row[0]: row[1] for row in by_status},
            "by_priority_band": {row[0]: row[1] for row in by_priority_band},
            "cases_awaiting_review": awaiting_review,
            "cases_eligible_for_rag_research": eligible_rag,
            "cases_eligible_for_training_assessment": eligible_training,
        }

    def tamil_capability_summary(self) -> dict[str, Any]:
        with self.transaction() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_cases WHERE language = 'ta' "
                "AND event_type IN ('language_failure','knowledge_gap')"
            ).fetchone()[0]
            boosted = connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_cases "
                "WHERE priority_reason_codes_json LIKE '%TAMIL_FIRST_PRIORITY_APPLIED%'"
            ).fetchone()[0]
        return {"tamil_capability_cases": total, "tamil_first_priority_boosted": boosted}

    def web_demand_summary(self) -> dict[str, Any]:
        with self.transaction() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_cases WHERE event_type = 'web_capability_gap'"
            ).fetchone()[0]
            frequency = connection.execute(
                "SELECT COALESCE(SUM(frequency),0) FROM knowledge_gap_cases "
                "WHERE event_type = 'web_capability_gap'"
            ).fetchone()[0]
        return {"web_capability_gap_cases": total, "total_occurrences": frequency}

    def tool_demand_summary(self) -> dict[str, Any]:
        with self.transaction() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_cases WHERE event_type = 'tool_capability_gap'"
            ).fetchone()[0]
            frequency = connection.execute(
                "SELECT COALESCE(SUM(frequency),0) FROM knowledge_gap_cases "
                "WHERE event_type = 'tool_capability_gap'"
            ).fetchone()[0]
        return {"tool_capability_gap_cases": total, "total_occurrences": frequency}

    def language_failure_summary(self) -> dict[str, Any]:
        with self.transaction() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_cases WHERE event_type = 'language_failure'"
            ).fetchone()[0]
        return {"language_failure_cases": total}

    # -- internal helpers

    @staticmethod
    def _case_row_id(connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM knowledge_gap_cases WHERE public_id = ?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"knowledge gap case not found: {public_id}")
        return row["id"]

    @staticmethod
    def _cluster_row_id(connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM knowledge_gap_clusters WHERE public_id = ?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"knowledge gap cluster not found: {public_id}")
        return row["id"]


__all__ = ["KnowledgeGapRepository"]
