"""Repository for the Phase 5 (Data Studio) Semantic Chunk Studio:
``semantic_chunks``, ``semantic_chunk_revisions``,
``semantic_chunk_relations``, ``semantic_chunk_reviews``, and
``semantic_chunk_events``. Mirrors
``backend/database/repositories/manual_data.py``'s shape exactly.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "chunk_id",
    "document_source_id",
    "data_source_id",
    "active_revision_id",
    "parent_chunk_id",
    "document_page_id",
    "extraction_id",
    "page_revision_id",
    "source_chunk_id",
    "target_chunk_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("semantic chunk row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class SemanticChunkRepository(BaseRepository):
    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        with super().transaction(immediate=immediate) as connection:
            yield connection

    # --- semantic_chunks ---------------------------------------------

    def create_chunk(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO semantic_chunks(
            public_id,chunk_code,document_source_id,data_source_id,chunk_type,
            parent_chunk_id,reading_order,language,domain,topic,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["chunk_code"],
                values["document_source_id"],
                values["data_source_id"],
                values.get("chunk_type", "unknown"),
                values.get("parent_chunk_id"),
                values.get("reading_order", 0),
                values.get("language", "unknown"),
                values.get("domain", ""),
                values.get("topic", ""),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def chunk(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM semantic_chunks WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("semantic chunk not found")
        return row

    def chunk_by_id(self, connection: sqlite3.Connection, chunk_id: int) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM semantic_chunks WHERE id=?", (chunk_id,)).fetchone()
        if not row:
            raise NotFoundError("semantic chunk not found")
        return row

    def parent_id_of(self, connection: sqlite3.Connection, chunk_id: int) -> int | None:
        row = connection.execute(
            "SELECT parent_chunk_id FROM semantic_chunks WHERE id=?", (chunk_id,)
        ).fetchone()
        return row["parent_chunk_id"] if row else None

    def list_chunks(
        self,
        connection: sqlite3.Connection,
        *,
        document_source_id: int | None = None,
        status: str | None = None,
        chunk_type: str | None = None,
        parent_chunk_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[sqlite3.Row], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if document_source_id is not None:
            clauses.append("document_source_id=?")
            params.append(document_source_id)
        if status:
            clauses.append("status=?")
            params.append(status)
        if chunk_type:
            clauses.append("chunk_type=?")
            params.append(chunk_type)
        if parent_chunk_id is not None:
            clauses.append("parent_chunk_id=?")
            params.append(parent_chunk_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = connection.execute(
            f"SELECT COUNT(*) FROM semantic_chunks {where}",  # noqa: S608
            params,
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM semantic_chunks {where} "  # noqa: S608
            "ORDER BY reading_order ASC, id ASC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return rows, total

    def update_chunk(
        self, connection: sqlite3.Connection, chunk_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        assignments = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE semantic_chunks SET {assignments},updated_at=CURRENT_TIMESTAMP "  # noqa: S608
            "WHERE id=?",
            (*fields.values(), chunk_id),
        )

    # --- semantic_chunk_revisions --------------------------------------

    def create_revision(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO semantic_chunk_revisions(
            public_id,chunk_id,revision_number,text,normalized_text,content_hash,
            document_page_id,page_number,extraction_id,page_revision_id,
            start_locator_json,end_locator_json,generation_method,confidence,
            warnings_json,metadata_json,change_summary,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["chunk_id"],
                values["revision_number"],
                values["text"],
                values["normalized_text"],
                values["content_hash"],
                values.get("document_page_id"),
                values.get("page_number"),
                values.get("extraction_id"),
                values.get("page_revision_id"),
                values.get("start_locator_json", "{}"),
                values.get("end_locator_json", "{}"),
                values.get("generation_method", "manual"),
                values.get("confidence"),
                values.get("warnings_json", "[]"),
                values.get("metadata_json", "{}"),
                values.get("change_summary", ""),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def revision(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM semantic_chunk_revisions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("semantic chunk revision not found")
        return row

    def revision_by_id(self, connection: sqlite3.Connection, revision_id: int) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM semantic_chunk_revisions WHERE id=?", (revision_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("semantic chunk revision not found")
        return row

    def list_revisions(self, connection: sqlite3.Connection, chunk_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM semantic_chunk_revisions WHERE chunk_id=? ORDER BY revision_number DESC",
            (chunk_id,),
        ).fetchall()

    def latest_revision_number(self, connection: sqlite3.Connection, chunk_id: int) -> int:
        row = connection.execute(
            "SELECT MAX(revision_number) AS n FROM semantic_chunk_revisions WHERE chunk_id=?",
            (chunk_id,),
        ).fetchone()
        return row["n"] or 0

    def content_hashes_for_document(
        self, connection: sqlite3.Connection, document_source_id: int
    ) -> dict[str, str]:
        """Maps chunk public_id -> its active revision's content_hash, for
        exact-duplicate detection within one document. Excludes
        `excluded`/`rejected`/`archived` chunks -- a superseded chunk must
        never trigger a false-positive duplicate warning against the
        chunk that replaced it."""
        rows = connection.execute(
            """SELECT c.public_id AS chunk_public_id, r.content_hash AS content_hash
            FROM semantic_chunks c JOIN semantic_chunk_revisions r ON r.id=c.active_revision_id
            WHERE c.document_source_id=?
            AND c.status NOT IN ('excluded','rejected','archived')""",
            (document_source_id,),
        ).fetchall()
        return {row["chunk_public_id"]: row["content_hash"] for row in rows}

    def locators_for_document(
        self, connection: sqlite3.Connection, document_source_id: int
    ) -> list[dict[str, Any]]:
        """Excludes `excluded`/`rejected`/`archived` chunks -- a chunk that
        has been superseded (e.g. absorbed into another chunk by a merge)
        is no longer part of the document's *current* chunk set, so its
        stale locator must not produce a false-positive overlap warning
        against the chunk that replaced it."""
        rows = connection.execute(
            """SELECT c.public_id AS public_id, r.page_number AS page_number,
            r.start_locator_json AS start_locator_json, r.end_locator_json AS end_locator_json
            FROM semantic_chunks c JOIN semantic_chunk_revisions r ON r.id=c.active_revision_id
            WHERE c.document_source_id=?
            AND c.status NOT IN ('excluded','rejected','archived')""",
            (document_source_id,),
        ).fetchall()
        results = []
        for row in rows:
            start = loads_json(row["start_locator_json"])
            end = loads_json(row["end_locator_json"])
            results.append(
                {
                    "public_id": row["public_id"],
                    "page_number": row["page_number"],
                    "offset_start": start.get("offset"),
                    "offset_end": end.get("offset"),
                }
            )
        return results

    # --- semantic_chunk_relations ---------------------------------------

    def create_relation(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO semantic_chunk_relations(
            public_id,source_chunk_id,target_chunk_id,relationship_type,sort_order,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["source_chunk_id"],
                values["target_chunk_id"],
                values["relationship_type"],
                values.get("sort_order", 0),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def list_relations(self, connection: sqlite3.Connection, chunk_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM semantic_chunk_relations WHERE source_chunk_id=? OR target_chunk_id=? "
            "ORDER BY sort_order ASC, id ASC",
            (chunk_id, chunk_id),
        ).fetchall()

    def delete_relation(self, connection: sqlite3.Connection, relation_id: int) -> None:
        connection.execute("DELETE FROM semantic_chunk_relations WHERE id=?", (relation_id,))

    # --- semantic_chunk_reviews / events ---------------------------------

    def create_review(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO semantic_chunk_reviews(
            public_id,chunk_id,action,status_after,notes,performed_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["chunk_id"],
                values["action"],
                values["status_after"],
                values.get("notes", ""),
                values["performed_by_admin_public_id"],
            ),
        )
        return public_id

    def list_reviews(self, connection: sqlite3.Connection, chunk_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM semantic_chunk_reviews WHERE chunk_id=? ORDER BY created_at DESC",
            (chunk_id,),
        ).fetchall()

    def add_event(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO semantic_chunk_events(
            public_id,chunk_id,event_type,performed_by_admin_public_id,notes,metadata_json)
            VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["chunk_id"],
                values["event_type"],
                values["performed_by_admin_public_id"],
                values.get("notes", ""),
                values.get("metadata_json", "{}"),
            ),
        )
        return public_id

    def list_events(self, connection: sqlite3.Connection, chunk_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM semantic_chunk_events WHERE chunk_id=? ORDER BY created_at DESC",
            (chunk_id,),
        ).fetchall()
