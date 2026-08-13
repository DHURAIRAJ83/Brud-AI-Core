"""Repository for MB-02: Brud Knowledge Core.

Structured storage and structured search only -- every query here is
a parameterized SQL WHERE/LIKE filter, never a vector or embedding
lookup. Independent of admin_assistant_*/inference_runtime_* tables,
same discipline as MB-01's own mini_brain.py repository.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {"id", "domain_id"}
JSON_LIST_FIELDS = (
    "keywords", "tags", "related_features", "related_apis",
    "related_services", "related_documentation",
)


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("mini brain knowledge row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class MiniBrainKnowledgeRepository(BaseRepository):
    # -- domains ---------------------------------------------------------

    def create_domain(self, connection: sqlite3.Connection, *, key: str, name: str, description: str) -> str:
        public_id = str(uuid4())
        connection.execute(
            "INSERT INTO mini_brain_knowledge_domains(public_id, key, name, description) "
            "VALUES (?, ?, ?, ?)",
            (public_id, key, name, description),
        )
        return public_id

    def domain_by_key(self, connection: sqlite3.Connection, key: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM mini_brain_knowledge_domains WHERE key=?", (key,)
        ).fetchone()

    def list_domains(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM mini_brain_knowledge_domains ORDER BY name"
        ).fetchall()

    def domain(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_knowledge_domains WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"knowledge domain not found: {public_id}")
        return row

    # -- items -------------------------------------------------------------

    def create_item(
        self, connection: sqlite3.Connection, *, domain_id: int, payload: dict[str, Any],
        admin_public_id: str | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_knowledge_items(
                public_id, domain_id, title, category, description,
                keywords_json, tags_json, related_features_json, related_apis_json,
                related_services_json, related_documentation_json, source, version,
                status, created_by_admin_public_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id, domain_id, payload["title"], payload["category"],
                payload.get("description", ""),
                dumps_json(payload.get("keywords", [])), dumps_json(payload.get("tags", [])),
                dumps_json(payload.get("related_features", [])),
                dumps_json(payload.get("related_apis", [])),
                dumps_json(payload.get("related_services", [])),
                dumps_json(payload.get("related_documentation", [])),
                payload.get("source", ""), payload.get("version", "1.0"),
                payload.get("status", "active"), admin_public_id,
            ),
        )
        return public_id

    def item(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_knowledge_items WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"knowledge item not found: {public_id}")
        return row

    def item_by_title(
        self, connection: sqlite3.Connection, domain_id: int, title: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM mini_brain_knowledge_items WHERE domain_id=? AND title=?",
            (domain_id, title),
        ).fetchone()

    def list_items(
        self, connection: sqlite3.Connection, *, domain_id: int | None = None,
        limit: int = 100, offset: int = 0,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        if domain_id is not None:
            return connection.execute(
                "SELECT * FROM mini_brain_knowledge_items WHERE domain_id=? "
                "ORDER BY title LIMIT ? OFFSET ?",
                (domain_id, limit, offset),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM mini_brain_knowledge_items ORDER BY title LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def all_items(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute("SELECT * FROM mini_brain_knowledge_items").fetchall()

    def search_items(
        self, connection: sqlite3.Connection, *, query: str | None, category: str | None,
        tag: str | None, domain_key: str | None, status: str | None,
        limit: int = 50, offset: int = 0,
    ) -> list[sqlite3.Row]:
        """Structured search only: exact/LIKE matches on title, category,
        source, and JSON-encoded keyword/tag lists. No ranking model, no
        similarity score -- results are ordered by title alone."""

        limit, offset = self.pagination(limit, offset)
        clauses = []
        params: list[Any] = []
        joins = ""
        if domain_key is not None:
            joins = " JOIN mini_brain_knowledge_domains d ON d.id = i.domain_id"
            clauses.append("d.key = ?")
            params.append(domain_key)
        if category is not None:
            clauses.append("i.category = ?")
            params.append(category)
        if status is not None:
            clauses.append("i.status = ?")
            params.append(status)
        if tag is not None:
            clauses.append("i.tags_json LIKE ?")
            params.append(f'%"{tag}"%')
        if query is not None and query.strip():
            like = f"%{query.strip()}%"
            clauses.append(
                "(i.title LIKE ? OR i.description LIKE ? OR i.keywords_json LIKE ? "
                "OR i.source LIKE ? OR i.related_apis_json LIKE ? OR i.related_services_json LIKE ?)"
            )
            params.extend([like, like, like, like, like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        return connection.execute(
            f"SELECT i.* FROM mini_brain_knowledge_items i{joins} {where} "
            "ORDER BY i.title LIMIT ? OFFSET ?",
            params,
        ).fetchall()

    # -- relationships -------------------------------------------------------

    def create_relationship(
        self, connection: sqlite3.Connection, *, from_item_id: int, to_item_id: int,
        relationship_type: str, description: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_knowledge_relationships(
                public_id, from_item_id, to_item_id, relationship_type, description
            ) VALUES (?, ?, ?, ?, ?)""",
            (public_id, from_item_id, to_item_id, relationship_type, description),
        )
        return public_id

    def all_relationships(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute("SELECT * FROM mini_brain_knowledge_relationships").fetchall()

    def relationships_for_item(
        self, connection: sqlite3.Connection, item_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM mini_brain_knowledge_relationships "
            "WHERE from_item_id=? OR to_item_id=?",
            (item_id, item_id),
        ).fetchall()

    # -- validation reports ---------------------------------------------------

    def record_validation_report(
        self, connection: sqlite3.Connection, *, issues: list[dict[str, Any]],
        summary: dict[str, Any], admin_public_id: str | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_knowledge_validation_reports(
                public_id, triggered_by_admin_public_id, issues_json, summary_json
            ) VALUES (?, ?, ?, ?)""",
            (public_id, admin_public_id, dumps_json(issues), dumps_json(summary)),
        )
        return public_id

    def latest_validation_report(self, connection: sqlite3.Connection) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM mini_brain_knowledge_validation_reports ORDER BY id DESC LIMIT 1"
        ).fetchone()

    def list_validation_reports(
        self, connection: sqlite3.Connection, *, limit: int = 10, offset: int = 0
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_knowledge_validation_reports "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def is_seeded(self, connection: sqlite3.Connection) -> bool:
        return connection.execute(
            "SELECT 1 FROM mini_brain_knowledge_domains LIMIT 1"
        ).fetchone() is not None
