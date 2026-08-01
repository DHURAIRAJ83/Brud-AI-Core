"""Phase 20 persistence for Trusted Web search/evidence/fetch/policy
events and the Deterministic Tool execution log (migration 042). Every
table here is append-only (mirrors `knowledge_gap.py`'s own
convention for its append-only tables) -- nothing in this module ever
UPDATEs or DELETEs a row; the DB triggers enforce this independently
of application code discipline. No raw page content or raw calculator/
conversion/date input beyond a bounded, non-PII summary is ever
written here.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.database.repositories.base import BaseRepository, NotFoundError


def _search_event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "request_id": row["request_id"],
        "query_hash": row["query_hash"],
        "web_category": row["web_category"],
        "provider_name": row["provider_name"],
        "policy_version": row["policy_version"],
        "status": row["status"],
        "result_count": row["result_count"],
        "conflict_status": row["conflict_status"],
        "overall_freshness_status": row["overall_freshness_status"],
        "latency_ms": row["latency_ms"],
        "created_at": row["created_at"],
    }


def _evidence_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "source_url_normalized": row["source_url_normalized"],
        "source_domain": row["source_domain"],
        "title": row["title"],
        "published_at": row["published_at"],
        "updated_at": row["updated_at"],
        "retrieved_at": row["retrieved_at"],
        "trust_level": row["trust_level"],
        "verification_level": row["verification_level"],
        "freshness_status": row["freshness_status"],
        "support_status": row["support_status"],
        "content_hash": row["content_hash"],
        "excerpt_redacted": row["excerpt_redacted"],
        "created_at": row["created_at"],
    }


def _fetch_event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "url_domain": row["url_domain"],
        "http_status": row["http_status"],
        "content_type": row["content_type"],
        "outcome": row["outcome"],
        "block_reason": row["block_reason"],
        "injection_status": row["injection_status"],
        "bytes_fetched": row["bytes_fetched"],
        "created_at": row["created_at"],
    }


def _policy_event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "event_type": row["event_type"],
        "policy_version": row["policy_version"],
        "policy_checksum_sha256": row["policy_checksum_sha256"],
        "admin_public_id": row["admin_public_id"],
        "detail": row["detail"],
        "created_at": row["created_at"],
    }


def _tool_execution_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "request_id": row["request_id"],
        "tool_name": row["tool_name"],
        "tool_version": row["tool_version"],
        "status": row["status"],
        "input_summary": row["input_summary"],
        "result_summary": row["result_summary"],
        "error_code": row["error_code"],
        "latency_ms": row["latency_ms"],
        "created_at": row["created_at"],
    }


def _capability_resolution_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "resolution_kind": row["resolution_kind"],
        "matched_by": row["matched_by"],
        "confidence_band": row["confidence_band"],
        "linked_by_admin_public_id": row["linked_by_admin_public_id"],
        "created_at": row["created_at"],
    }


class TrustedWebToolGatewayRepository(BaseRepository):
    # -- trusted web: search events --------------------------------------------------------

    def record_search_event(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO trusted_web_search_events(
                    public_id, request_id, query_hash, web_category, provider_name,
                    policy_version, status, result_count, conflict_status,
                    overall_freshness_status, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    values["request_id"],
                    values["query_hash"],
                    values["web_category"],
                    values.get("provider_name"),
                    values["policy_version"],
                    values["status"],
                    values.get("result_count", 0),
                    values.get("conflict_status", "no_conflict"),
                    values.get("overall_freshness_status"),
                    values.get("latency_ms"),
                ),
            )
        return {"public_id": public_id, **values}

    def _search_event_row_id(self, connection: sqlite3.Connection, public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM trusted_web_search_events WHERE public_id = ?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"trusted web search event not found: {public_id}")
        return row["id"]

    def get_search_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM trusted_web_search_events WHERE public_id = ?", (public_id,)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"trusted web search event not found: {public_id}")
        return _search_event_public(row)

    def list_search_events(self, *, limit: int, offset: int) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM trusted_web_search_events ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_search_event_public(row) for row in rows]

    # -- trusted web: source evidence -------------------------------------------------------

    def record_source_evidence(
        self, search_event_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            search_event_id = self._search_event_row_id(connection, search_event_public_id)
            connection.execute(
                """INSERT INTO trusted_web_source_evidence(
                    public_id, search_event_id, source_url_normalized, source_domain, title,
                    published_at, updated_at, retrieved_at, trust_level, verification_level,
                    freshness_status, support_status, content_hash, excerpt_redacted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    search_event_id,
                    values["source_url_normalized"],
                    values["source_domain"],
                    values.get("title"),
                    values.get("published_at"),
                    values.get("updated_at"),
                    values["retrieved_at"],
                    values["trust_level"],
                    values["verification_level"],
                    values["freshness_status"],
                    values["support_status"],
                    values.get("content_hash"),
                    values.get("excerpt_redacted"),
                ),
            )
        return {"public_id": public_id, **values}

    def list_evidence_for_search_event(self, search_event_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            search_event_id = self._search_event_row_id(connection, search_event_public_id)
            rows = connection.execute(
                "SELECT * FROM trusted_web_source_evidence WHERE search_event_id = ? ORDER BY id",
                (search_event_id,),
            ).fetchall()
        return [_evidence_public(row) for row in rows]

    def list_recent_evidence(self, *, limit: int, offset: int) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM trusted_web_source_evidence ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_evidence_public(row) for row in rows]

    # -- trusted web: fetch events -----------------------------------------------------------

    def record_fetch_event(
        self, search_event_public_id: str | None, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            search_event_id = (
                self._search_event_row_id(connection, search_event_public_id)
                if search_event_public_id
                else None
            )
            connection.execute(
                """INSERT INTO trusted_web_fetch_events(
                    public_id, search_event_id, url_domain, http_status, content_type,
                    outcome, block_reason, injection_status, bytes_fetched
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    search_event_id,
                    values["url_domain"],
                    values.get("http_status"),
                    values.get("content_type"),
                    values["outcome"],
                    values.get("block_reason"),
                    values.get("injection_status"),
                    values.get("bytes_fetched", 0),
                ),
            )
        return {"public_id": public_id, **values}

    def list_fetch_events(self, *, limit: int, offset: int) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM trusted_web_fetch_events ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_fetch_event_public(row) for row in rows]

    # -- trusted web: policy events -----------------------------------------------------------

    def record_policy_event(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO trusted_web_policy_events(
                    public_id, event_type, policy_version, policy_checksum_sha256,
                    admin_public_id, detail
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    values["event_type"],
                    values.get("policy_version"),
                    values.get("policy_checksum_sha256"),
                    values.get("admin_public_id"),
                    values.get("detail"),
                ),
            )
        return {"public_id": public_id, **values}

    def list_policy_events(self, *, limit: int, offset: int) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM trusted_web_policy_events ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_policy_event_public(row) for row in rows]

    # -- deterministic tool execution ---------------------------------------------------------

    def record_tool_execution(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO deterministic_tool_execution_events(
                    public_id, request_id, tool_name, tool_version, status,
                    input_summary, result_summary, error_code, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    values["request_id"],
                    values["tool_name"],
                    values["tool_version"],
                    values["status"],
                    values.get("input_summary"),
                    values.get("result_summary"),
                    values.get("error_code"),
                    values.get("latency_ms"),
                ),
            )
        return {"public_id": public_id, **values}

    def get_tool_execution(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM deterministic_tool_execution_events WHERE public_id = ?",
                (public_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"tool execution event not found: {public_id}")
        return _tool_execution_public(row)

    def list_tool_executions(
        self, *, limit: int, offset: int, tool_name: str | None = None
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        with self.transaction() as connection:
            if tool_name:
                rows = connection.execute(
                    "SELECT * FROM deterministic_tool_execution_events WHERE tool_name = ? "
                    "ORDER BY id DESC LIMIT ? OFFSET ?",
                    (tool_name, limit, offset),
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM deterministic_tool_execution_events "
                    "ORDER BY id DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                ).fetchall()
        return [_tool_execution_public(row) for row in rows]

    # -- knowledge-gap capability resolution linkage ------------------------------------------

    def record_capability_resolution(
        self, case_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            case_row = connection.execute(
                "SELECT id FROM knowledge_gap_cases WHERE public_id = ?", (case_public_id,)
            ).fetchone()
            if case_row is None:
                raise NotFoundError(f"knowledge gap case not found: {case_public_id}")
            search_event_id = None
            if values.get("search_event_public_id"):
                search_event_id = self._search_event_row_id(
                    connection, values["search_event_public_id"]
                )
            tool_execution_id = None
            if values.get("tool_execution_public_id"):
                tool_row = connection.execute(
                    "SELECT id FROM deterministic_tool_execution_events WHERE public_id = ?",
                    (values["tool_execution_public_id"],),
                ).fetchone()
                if tool_row is None:
                    raise NotFoundError(
                        f"tool execution event not found: {values['tool_execution_public_id']}"
                    )
                tool_execution_id = tool_row["id"]
            connection.execute(
                """INSERT INTO knowledge_gap_capability_resolutions(
                    public_id, case_id, resolution_kind, search_event_id, tool_execution_id,
                    matched_by, confidence_band, linked_by_admin_public_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    case_row["id"],
                    values["resolution_kind"],
                    search_event_id,
                    tool_execution_id,
                    values["matched_by"],
                    values.get("confidence_band", "medium"),
                    values.get("linked_by_admin_public_id"),
                ),
            )
        return {"public_id": public_id, "case_public_id": case_public_id, **values}

    def list_capability_resolutions_for_case(self, case_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            case_row = connection.execute(
                "SELECT id FROM knowledge_gap_cases WHERE public_id = ?", (case_public_id,)
            ).fetchone()
            if case_row is None:
                raise NotFoundError(f"knowledge gap case not found: {case_public_id}")
            rows = connection.execute(
                "SELECT * FROM knowledge_gap_capability_resolutions WHERE case_id = ? "
                "ORDER BY id DESC",
                (case_row["id"],),
            ).fetchall()
        return [_capability_resolution_public(row) for row in rows]

    # -- aggregate overviews (Admin Dashboard / Data Overview) --------------------------------

    def trusted_web_overview(self) -> dict[str, Any]:
        with self.transaction() as connection:
            total = connection.execute("SELECT COUNT(*) FROM trusted_web_search_events").fetchone()[
                0
            ]
            by_status = connection.execute(
                "SELECT status, COUNT(*) AS n FROM trusted_web_search_events GROUP BY status"
            ).fetchall()
            by_category = connection.execute(
                "SELECT web_category, COUNT(*) AS n FROM trusted_web_search_events "
                "GROUP BY web_category"
            ).fetchall()
            conflicts = connection.execute(
                "SELECT conflict_status, COUNT(*) AS n FROM trusted_web_search_events "
                "WHERE conflict_status != 'no_conflict' GROUP BY conflict_status"
            ).fetchall()
            blocked_fetches = connection.execute(
                "SELECT COUNT(*) FROM trusted_web_fetch_events WHERE outcome = 'blocked'"
            ).fetchone()[0]
            injection_blocks = connection.execute(
                "SELECT COUNT(*) FROM trusted_web_fetch_events WHERE injection_status = 'blocked'"
            ).fetchone()[0]
            resolved_web_gaps = connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_capability_resolutions "
                "WHERE resolution_kind = 'resolved_by_trusted_web'"
            ).fetchone()[0]
        return {
            "total_search_events": total,
            "by_status": {row["status"]: row["n"] for row in by_status},
            "by_category": {row["web_category"]: row["n"] for row in by_category},
            "conflicts": {row["conflict_status"]: row["n"] for row in conflicts},
            "blocked_fetches": blocked_fetches,
            "injection_blocked_sources": injection_blocks,
            "resolved_web_capability_gaps": resolved_web_gaps,
        }

    def tool_gateway_overview(self) -> dict[str, Any]:
        with self.transaction() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM deterministic_tool_execution_events"
            ).fetchone()[0]
            by_tool = connection.execute(
                "SELECT tool_name, COUNT(*) AS n FROM deterministic_tool_execution_events "
                "GROUP BY tool_name"
            ).fetchall()
            by_status = connection.execute(
                "SELECT status, COUNT(*) AS n FROM deterministic_tool_execution_events "
                "GROUP BY status"
            ).fetchall()
            resolved_tool_gaps = connection.execute(
                "SELECT COUNT(*) FROM knowledge_gap_capability_resolutions "
                "WHERE resolution_kind = 'resolved_by_tool'"
            ).fetchone()[0]
        return {
            "total_executions": total,
            "by_tool": {row["tool_name"]: row["n"] for row in by_tool},
            "by_status": {row["status"]: row["n"] for row in by_status},
            "resolved_tool_capability_gaps": resolved_tool_gaps,
        }

    def web_verification_summary(self) -> dict[str, Any]:
        with self.transaction() as connection:
            by_level = connection.execute(
                "SELECT verification_level, COUNT(*) AS n FROM trusted_web_source_evidence "
                "GROUP BY verification_level"
            ).fetchall()
        return {"by_verification_level": {row["verification_level"]: row["n"] for row in by_level}}

    def web_freshness_summary(self) -> dict[str, Any]:
        with self.transaction() as connection:
            by_freshness = connection.execute(
                "SELECT overall_freshness_status, COUNT(*) AS n FROM trusted_web_search_events "
                "WHERE overall_freshness_status IS NOT NULL GROUP BY overall_freshness_status"
            ).fetchall()
        return {
            "by_freshness_status": {
                row["overall_freshness_status"]: row["n"] for row in by_freshness
            }
        }


__all__ = ["TrustedWebToolGatewayRepository"]
