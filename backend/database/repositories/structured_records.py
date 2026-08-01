"""Repository for the Phase 5 (Data Studio) Structured Record Candidate
staging layer: ``structured_record_candidates``,
``structured_record_candidate_chunks``,
``structured_record_candidate_revisions``, ``structured_record_reviews``.
Mirrors ``backend/database/repositories/manual_data.py``'s shape exactly
-- see docs/data_studio/phase5_semantic_chunk_structured_record_plan.md
section 4 for why this is its own staging table rather than a retrofit
of ``manual_data_records``.
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
    "candidate_id",
    "data_source_id",
    "document_source_id",
    "primary_chunk_id",
    "active_revision_id",
    "chunk_id",
    "revision_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("structured record row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class StructuredRecordRepository(BaseRepository):
    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        with super().transaction(immediate=immediate) as connection:
            yield connection

    # --- structured_record_candidates -------------------------------------

    def create_candidate(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO structured_record_candidates(
            public_id,candidate_code,record_type,data_source_id,document_source_id,
            primary_chunk_id,requested_uses_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["candidate_code"],
                values["record_type"],
                values["data_source_id"],
                values.get("document_source_id"),
                values.get("primary_chunk_id"),
                values.get("requested_uses_json", "[]"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def candidate(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM structured_record_candidates WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("structured record candidate not found")
        return row

    def candidate_by_id(self, connection: sqlite3.Connection, candidate_id: int) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM structured_record_candidates WHERE id=?", (candidate_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("structured record candidate not found")
        return row

    def list_candidates(
        self,
        connection: sqlite3.Connection,
        *,
        status: str | None = None,
        record_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[sqlite3.Row], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if record_type:
            clauses.append("record_type=?")
            params.append(record_type)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = connection.execute(
            f"SELECT COUNT(*) FROM structured_record_candidates {where}",  # noqa: S608
            params,
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM structured_record_candidates {where} "  # noqa: S608
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return rows, total

    def update_candidate(
        self, connection: sqlite3.Connection, candidate_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        assignments = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE structured_record_candidates SET {assignments},"  # noqa: S608
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (*fields.values(), candidate_id),
        )

    # --- structured_record_candidate_chunks -------------------------------

    def link_chunk(
        self,
        connection: sqlite3.Connection,
        candidate_id: int,
        chunk_id: int,
        *,
        role: str = "evidence",
        sort_order: int = 0,
    ) -> None:
        connection.execute(
            """INSERT OR IGNORE INTO structured_record_candidate_chunks(
            candidate_id,chunk_id,role,sort_order) VALUES (?,?,?,?)""",
            (candidate_id, chunk_id, role, sort_order),
        )

    def list_candidate_chunks(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT src.role AS role, src.sort_order AS sort_order,
            c.public_id AS chunk_public_id, c.chunk_type AS chunk_type
            FROM structured_record_candidate_chunks src
            JOIN semantic_chunks c ON c.id = src.chunk_id
            WHERE src.candidate_id=? ORDER BY src.sort_order ASC""",
            (candidate_id,),
        ).fetchall()

    # --- structured_record_candidate_revisions ----------------------------

    REVISION_FIELDS = (
        "title",
        "text",
        "question",
        "answer",
        "instruction",
        "context",
        "response",
        "word",
        "part_of_speech",
        "meanings_json",
        "examples_json",
        "synonyms_json",
        "antonyms_json",
        "related_words_json",
        "source_language",
        "source_text",
        "target_language",
        "target_text",
        "tanglish_text",
        "normalized_tamil",
        "english_meaning",
        "grammar_rule",
        "correct_example",
        "incorrect_example",
        "correction",
        "origin",
        "metadata_json",
        "change_summary",
    )

    _REVISION_JSON_DEFAULTS = {
        "meanings_json": "[]",
        "examples_json": "[]",
        "synonyms_json": "[]",
        "antonyms_json": "[]",
        "related_words_json": "[]",
        "metadata_json": "{}",
    }

    def create_revision(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        columns = ["public_id", "candidate_id", "revision_number", "content_hash"]
        params: list[Any] = [
            public_id,
            values["candidate_id"],
            values["revision_number"],
            values["content_hash"],
        ]
        for field in self.REVISION_FIELDS:
            columns.append(field)
            if field == "origin":
                params.append(values.get(field, "source_grounded"))
            elif field == "change_summary":
                params.append(values.get(field, ""))
            elif field in self._REVISION_JSON_DEFAULTS:
                params.append(values.get(field, self._REVISION_JSON_DEFAULTS[field]))
            else:
                params.append(values.get(field))
        columns.append("created_by_admin_public_id")
        params.append(values["created_by_admin_public_id"])
        placeholders = ",".join("?" for _ in columns)
        connection.execute(
            f"INSERT INTO structured_record_candidate_revisions({','.join(columns)}) "  # noqa: S608
            f"VALUES ({placeholders})",
            params,
        )
        return public_id

    def revision(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM structured_record_candidate_revisions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("structured record revision not found")
        return row

    def revision_by_id(self, connection: sqlite3.Connection, revision_id: int) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM structured_record_candidate_revisions WHERE id=?", (revision_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("structured record revision not found")
        return row

    def list_revisions(
        self, connection: sqlite3.Connection, candidate_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM structured_record_candidate_revisions WHERE candidate_id=? "
            "ORDER BY revision_number DESC",
            (candidate_id,),
        ).fetchall()

    def latest_revision_number(self, connection: sqlite3.Connection, candidate_id: int) -> int:
        row = connection.execute(
            "SELECT MAX(revision_number) AS n FROM structured_record_candidate_revisions "
            "WHERE candidate_id=?",
            (candidate_id,),
        ).fetchone()
        return row["n"] or 0

    def content_hash_exists(
        self, connection: sqlite3.Connection, record_type: str, content_hash: str
    ) -> str | None:
        row = connection.execute(
            """SELECT sc.public_id AS public_id FROM structured_record_candidate_revisions r
            JOIN structured_record_candidates sc ON sc.id = r.candidate_id
            WHERE sc.record_type=? AND r.content_hash=? ORDER BY r.id DESC LIMIT 1""",
            (record_type, content_hash),
        ).fetchone()
        return row["public_id"] if row else None

    def list_by_type(
        self, connection: sqlite3.Connection, record_type: str
    ) -> list[dict[str, Any]]:
        """Active-revision snapshot of every candidate of one type, for
        conflict detection (dictionary senses, Q&A, translations)."""
        rows = connection.execute(
            """SELECT sc.public_id AS public_id, r.* FROM structured_record_candidates sc
            JOIN structured_record_candidate_revisions r ON r.id = sc.active_revision_id
            WHERE sc.record_type=?""",
            (record_type,),
        ).fetchall()
        return [dict(row) for row in rows]

    # --- structured_record_reviews -----------------------------------------

    def create_review(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO structured_record_reviews(
            public_id,candidate_id,revision_id,review_status,comments,reviewer_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["candidate_id"],
                values["revision_id"],
                values["review_status"],
                values.get("comments", ""),
                values["reviewer_admin_public_id"],
            ),
        )
        return public_id

    def list_reviews(self, connection: sqlite3.Connection, candidate_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM structured_record_reviews WHERE candidate_id=? ORDER BY created_at DESC",
            (candidate_id,),
        ).fetchall()
