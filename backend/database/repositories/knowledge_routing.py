"""Persistence for `routing_classification_decisions` (Phase 17, migration
039). Never stores raw question/record text -- only the SHA-256
`input_hash` plus the already-computed, already-versioned classification
outputs. Append-only, matching `ProductionReadinessRepository`'s own
convention for diagnostic/audit-style tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError


def _decision_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "input_hash": row["input_hash"],
        "context_type": row["context_type"],
        "language_category": row["language_category"],
        "intent": row["intent"],
        "domain": row["domain"],
        "subdomain": row["subdomain"],
        "freshness": row["freshness"],
        "ambiguity": row["ambiguity"],
        "safety_risk": row["safety_risk"],
        "evidence_requirement": row["evidence_requirement"],
        "execution_route": row["execution_route"],
        "learning_target": row["learning_target"],
        "requires_human_review": bool(row["requires_human_review"]),
        "input_truncated": bool(row["input_truncated"]),
        "reason_codes": loads_json(row["reason_codes_json"]),
        "policy_version": row["policy_version"],
        "taxonomy_version": row["taxonomy_version"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
    }


_SELECT_COLUMNS = """
    public_id, input_hash, context_type, language_category, intent, domain, subdomain,
    freshness, ambiguity, safety_risk, evidence_requirement, execution_route, learning_target,
    requires_human_review, input_truncated, reason_codes_json, policy_version, taxonomy_version,
    created_by_admin_public_id, created_at
"""


class KnowledgeRoutingRepository(BaseRepository):
    def create_decision(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO routing_classification_decisions(
                    public_id, input_hash, context_type, language_category, intent, domain,
                    subdomain, freshness, ambiguity, safety_risk, evidence_requirement,
                    execution_route, learning_target, requires_human_review, input_truncated,
                    reason_codes_json, policy_version, taxonomy_version, created_by_admin_public_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    public_id,
                    values["input_hash"],
                    values["context_type"],
                    values["language_category"],
                    values["intent"],
                    values["domain"],
                    values.get("subdomain"),
                    values["freshness"],
                    values["ambiguity"],
                    values["safety_risk"],
                    values["evidence_requirement"],
                    values["execution_route"],
                    values["learning_target"],
                    1 if values.get("requires_human_review") else 0,
                    1 if values.get("input_truncated") else 0,
                    dumps_json(list(values.get("reason_codes", ()))),
                    values["policy_version"],
                    values["taxonomy_version"],
                    values.get("created_by_admin_public_id"),
                ),
            )
            row = connection.execute(
                f"SELECT {_SELECT_COLUMNS} FROM routing_classification_decisions "
                "WHERE public_id = ?",
                (public_id,),
            ).fetchone()
        return _decision_public(row)

    def get_decision(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                f"SELECT {_SELECT_COLUMNS} FROM routing_classification_decisions "
                "WHERE public_id = ?",
                (public_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"routing classification decision not found: {public_id}")
        return _decision_public(row)

    def list_decisions(
        self,
        *,
        limit: int,
        offset: int,
        context_type: str | None = None,
        execution_route: str | None = None,
        domain: str | None = None,
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if context_type:
            clauses.append("context_type = ?")
            params.append(context_type)
        if execution_route:
            clauses.append("execution_route = ?")
            params.append(execution_route)
        if domain:
            clauses.append("domain = ?")
            params.append(domain)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            rows = connection.execute(
                f"""SELECT {_SELECT_COLUMNS} FROM routing_classification_decisions
                {where} ORDER BY id DESC LIMIT ? OFFSET ?""",
                (*params, limit, offset),
            ).fetchall()
        return [_decision_public(row) for row in rows]

    def aggregate_metrics(self) -> dict[str, Any]:
        with self.transaction() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM routing_classification_decisions"
            ).fetchone()[0]
            by_route = connection.execute(
                "SELECT execution_route, COUNT(*) FROM routing_classification_decisions "
                "GROUP BY execution_route"
            ).fetchall()
            by_domain = connection.execute(
                "SELECT domain, COUNT(*) FROM routing_classification_decisions GROUP BY domain"
            ).fetchall()
            by_target = connection.execute(
                "SELECT learning_target, COUNT(*) FROM routing_classification_decisions "
                "GROUP BY learning_target"
            ).fetchall()
            review_count = connection.execute(
                "SELECT COUNT(*) FROM routing_classification_decisions "
                "WHERE requires_human_review = 1"
            ).fetchone()[0]
        return {
            "total_classifications": total,
            "by_execution_route": {row[0]: row[1] for row in by_route},
            "by_domain": {row[0]: row[1] for row in by_domain},
            "by_learning_target": {row[0]: row[1] for row in by_target},
            "requires_human_review_count": review_count,
        }


__all__ = ["KnowledgeRoutingRepository"]
