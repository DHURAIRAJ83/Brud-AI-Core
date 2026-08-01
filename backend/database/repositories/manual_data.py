"""Repository for the Phase 3 (Data Studio) Manual Data Studio:
``manual_data_records``, ``manual_data_record_revisions``,
``manual_data_reviews``, ``manual_data_verifications``,
``manual_data_usage_decisions``, and ``manual_data_events``. See
``docs/data_studio/phase3_manual_data_studio_plan.md`` for why this is a
staging layer in front of the existing ``dataset_records`` manual-entry
system rather than a second competing dataset-management system.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {"id", "record_id", "revision_id", "source_id", "active_revision_id"}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("manual data row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class ManualDataRepository(BaseRepository):
    """Defaults to ``immediate=True``, matching
    ``DataSourceRepository``: every method reads the current row and
    then conditionally writes within the same transaction, and no
    caller nests a second ``transaction()`` inside an already-open
    one."""

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        with super().transaction(immediate=immediate) as connection:
            yield connection

    # --- manual_data_records ---------------------------------------------

    def create_record(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO manual_data_records(
            public_id,record_code,record_type,source_id,primary_language,input_language,
            output_language,domain,topic,difficulty,audience,style,fact_dependency,
            knowledge_risk,creation_method,requested_uses_json,review_expiry_at,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["record_code"],
                values["record_type"],
                values["source_id"],
                values.get("primary_language", "unknown"),
                values.get("input_language"),
                values.get("output_language"),
                values.get("domain", ""),
                values.get("topic", ""),
                values.get("difficulty"),
                values.get("audience"),
                values.get("style"),
                values.get("fact_dependency", "none"),
                values.get("knowledge_risk", "language_only"),
                values.get("creation_method", "admin_created"),
                values.get("requested_uses_json", "[]"),
                values.get("review_expiry_at"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def record(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM manual_data_records WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("manual data record not found")
        return row

    def record_by_id(self, connection: sqlite3.Connection, record_id: int) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM manual_data_records WHERE id=?", (record_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("manual data record not found")
        return row

    def record_by_code(
        self, connection: sqlite3.Connection, record_code: str
    ) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT * FROM manual_data_records WHERE record_code=?", (record_code,)
        ).fetchone()

    def list_records(
        self,
        connection: sqlite3.Connection,
        *,
        status: str | None = None,
        record_type: str | None = None,
        creation_method: str | None = None,
        knowledge_risk: str | None = None,
        search: str | None = None,
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
        if creation_method:
            clauses.append("creation_method=?")
            params.append(creation_method)
        if knowledge_risk:
            clauses.append("knowledge_risk=?")
            params.append(knowledge_risk)
        if search:
            clauses.append("(record_code LIKE ? OR domain LIKE ? OR topic LIKE ?)")
            like = f"%{search}%"
            params.extend([like, like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = connection.execute(
            f"SELECT COUNT(*) FROM manual_data_records {where}",  # noqa: S608
            params,
        ).fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM manual_data_records {where} "  # noqa: S608
            "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return rows, total

    def summary_counts(self, connection: sqlite3.Connection) -> dict[str, int]:
        counts = {
            row["status"]: row["n"]
            for row in connection.execute(
                "SELECT status, COUNT(*) AS n FROM manual_data_records GROUP BY status"
            )
        }
        return counts

    def counts_by(self, connection: sqlite3.Connection, column: str) -> dict[str, int]:
        if column not in {"record_type", "primary_language", "creation_method", "knowledge_risk"}:
            raise ValueError(f"unsupported group-by column: {column}")
        return {
            row[column]: row["n"]
            for row in connection.execute(
                f"SELECT {column}, COUNT(*) AS n FROM manual_data_records "  # noqa: S608
                f"GROUP BY {column}"
            )
        }

    def update_record(
        self, connection: sqlite3.Connection, record_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE manual_data_records SET {columns}, updated_at=CURRENT_TIMESTAMP "  # noqa: S608
            "WHERE id=?",
            (*fields.values(), record_id),
        )

    # --- manual_data_record_revisions (append, never edited) -------------

    def create_revision(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO manual_data_record_revisions(
            public_id,record_id,revision_number,title,input_text,output_text,
            instruction_text,response_text,question_text,answer_text,tamil_text,
            english_text,tanglish_text,word,part_of_speech,meanings_json,examples_json,
            metadata_json,content_hash,change_summary,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["record_id"],
                values["revision_number"],
                values.get("title"),
                values.get("input_text"),
                values.get("output_text"),
                values.get("instruction_text"),
                values.get("response_text"),
                values.get("question_text"),
                values.get("answer_text"),
                values.get("tamil_text"),
                values.get("english_text"),
                values.get("tanglish_text"),
                values.get("word"),
                values.get("part_of_speech"),
                values.get("meanings_json", "[]"),
                values.get("examples_json", "[]"),
                values.get("metadata_json", "{}"),
                values["content_hash"],
                values.get("change_summary", ""),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def revision(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM manual_data_record_revisions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("manual data revision not found")
        return row

    def revision_by_id(self, connection: sqlite3.Connection, revision_id: int) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM manual_data_record_revisions WHERE id=?", (revision_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("manual data revision not found")
        return row

    def list_revisions(self, connection: sqlite3.Connection, record_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM manual_data_record_revisions WHERE record_id=? "
            "ORDER BY revision_number DESC",
            (record_id,),
        ).fetchall()

    def latest_revision_number(self, connection: sqlite3.Connection, record_id: int) -> int:
        row = connection.execute(
            "SELECT MAX(revision_number) FROM manual_data_record_revisions WHERE record_id=?",
            (record_id,),
        ).fetchone()
        return row[0] or 0

    def content_hash_exists(
        self,
        connection: sqlite3.Connection,
        content_hash: str,
        *,
        exclude_record_id: int | None = None,
    ) -> sqlite3.Row | None:
        if exclude_record_id is not None:
            return connection.execute(
                "SELECT r.* FROM manual_data_record_revisions r "
                "JOIN manual_data_records m ON m.active_revision_id = r.id "
                "WHERE r.content_hash=? AND m.id != ?",
                (content_hash, exclude_record_id),
            ).fetchone()
        return connection.execute(
            "SELECT r.* FROM manual_data_record_revisions r "
            "JOIN manual_data_records m ON m.active_revision_id = r.id "
            "WHERE r.content_hash=?",
            (content_hash,),
        ).fetchone()

    def dictionary_word_exists(
        self,
        connection: sqlite3.Connection,
        word_key: str,
        *,
        exclude_record_id: int | None = None,
    ) -> sqlite3.Row | None:
        params: list[Any] = [word_key]
        exclusion = ""
        if exclude_record_id is not None:
            exclusion = "AND m.id != ?"
            params.append(exclude_record_id)
        return connection.execute(
            "SELECT r.* FROM manual_data_record_revisions r "
            "JOIN manual_data_records m ON m.active_revision_id = r.id "
            f"WHERE m.record_type='dictionary_entry' AND "  # noqa: S608
            f"(m.primary_language || ':' || lower(r.word)) = ? {exclusion}",
            params,
        ).fetchone()

    # --- manual_data_reviews -----------------------------------------------

    def create_review(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO manual_data_reviews(
            public_id,record_id,revision_id,review_type,review_status,
            reviewer_admin_public_id,comments,language_score,meaning_score,
            naturalness_score,factual_score,source_score,overall_score)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["record_id"],
                values["revision_id"],
                values["review_type"],
                values["review_status"],
                values["reviewer_admin_public_id"],
                values.get("comments", ""),
                values.get("language_score"),
                values.get("meaning_score"),
                values.get("naturalness_score"),
                values.get("factual_score"),
                values.get("source_score"),
                values.get("overall_score"),
            ),
        )
        return public_id

    def list_reviews(self, connection: sqlite3.Connection, record_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM manual_data_reviews WHERE record_id=? ORDER BY created_at DESC, id DESC",
            (record_id,),
        ).fetchall()

    # --- manual_data_verifications ------------------------------------------

    def create_verification(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO manual_data_verifications(
            public_id,record_id,revision_id,verification_type,verification_status,
            source_id,verified_by_admin_public_id,verification_notes,verified_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["record_id"],
                values["revision_id"],
                values["verification_type"],
                values.get("verification_status", "pending"),
                values.get("source_id"),
                values.get("verified_by_admin_public_id"),
                values.get("verification_notes", ""),
                values.get("verified_at"),
            ),
        )
        return public_id

    def update_verification(
        self, connection: sqlite3.Connection, verification_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE manual_data_verifications SET {columns} WHERE id=?",  # noqa: S608
            (*fields.values(), verification_id),
        )

    def list_verifications(
        self, connection: sqlite3.Connection, record_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM manual_data_verifications WHERE record_id=? "
            "ORDER BY created_at DESC, id DESC",
            (record_id,),
        ).fetchall()

    # --- manual_data_usage_decisions (append-only) --------------------------

    def add_usage_decision(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO manual_data_usage_decisions(
            public_id,record_id,revision_id,target_use,allowed,decision_code,
            blocking_reasons_json,warnings_json,evaluated_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["record_id"],
                values["revision_id"],
                values["target_use"],
                1 if values["allowed"] else 0,
                values["decision_code"],
                values.get("blocking_reasons_json", "[]"),
                values.get("warnings_json", "[]"),
                values.get("evaluated_by_admin_public_id"),
            ),
        )
        return public_id

    def list_usage_decisions(
        self, connection: sqlite3.Connection, record_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM manual_data_usage_decisions WHERE record_id=? "
            "ORDER BY evaluated_at DESC, id DESC",
            (record_id,),
        ).fetchall()

    # --- manual_data_events (append-only) -----------------------------------

    def add_event(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO manual_data_events(
            public_id,record_id,event_type,status_before,status_after,
            performed_by_admin_public_id,notes,metadata_json)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["record_id"],
                values["event_type"],
                values.get("status_before"),
                values.get("status_after"),
                values["performed_by_admin_public_id"],
                values.get("notes", ""),
                values.get("metadata_json", "{}"),
            ),
        )
        return public_id

    def list_events(self, connection: sqlite3.Connection, record_id: int) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM manual_data_events WHERE record_id=? ORDER BY created_at DESC, id DESC",
            (record_id,),
        ).fetchall()
