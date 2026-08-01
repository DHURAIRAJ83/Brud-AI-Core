"""Parameterized persistence and safe public projections for documents."""

import math
import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

DOCUMENT_JSON = {"metadata_json"}
PAGE_JSON = {"warnings_json"}
JOB_JSON = {"selected_pages_json", "configuration_json"}
CANDIDATE_JSON = {"metadata_json", "validation_errors_json", "validation_warnings_json"}
# Phase 4 additions -- see docs/data_studio/phase4_pdf_research_workspace_plan.md.
EXTRACTION_JSON = {"preprocessing_metadata_json", "extraction_warnings_json"}
REVIEW_EVENT_JSON: set[str] = set()
REPEATED_ELEMENT_JSON = {"page_occurrences_json"}


def decode(row: sqlite3.Row, json_columns: set[str], internal: bool = False) -> dict[str, Any]:
    value = dict(row)
    for column in json_columns:
        if column in value:
            default = (
                [] if any(token in column for token in ("warnings", "errors", "pages")) else {}
            )
            value[column.removesuffix("_json")] = loads_json(value.pop(column), default=default)
    if not internal:
        for key in (
            "id",
            "document_source_id",
            "processing_job_id",
            "stored_filename",
            "document_page_id",
        ):
            value.pop(key, None)
    return value


class DocumentRepository(BaseRepository):
    def document(self, connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM document_sources WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("document not found")
        return row

    def page(self, connection, document_id: int, page_number: int) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM document_pages WHERE document_source_id=? AND page_number=?",
            (document_id, page_number),
        ).fetchone()
        if not row:
            raise NotFoundError("document page not found")
        return row

    def candidate(self, connection, document_id: int, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM document_candidates WHERE document_source_id=? AND public_id=?",
            (document_id, public_id),
        ).fetchone()
        if not row:
            raise NotFoundError("document candidate not found")
        return row

    def job(self, connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM document_processing_jobs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("document processing job not found")
        return row

    def sft_candidate(self, connection, document_id: int, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM document_sft_candidates WHERE document_source_id=? AND public_id=?",
            (document_id, public_id),
        ).fetchone()
        if not row:
            raise NotFoundError("document sft candidate not found")
        return row

    def tamil_quality_issue(self, connection, document_id: int, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM document_tamil_quality_issues "
            "WHERE document_source_id=? AND public_id=?",
            (document_id, public_id),
        ).fetchone()
        if not row:
            raise NotFoundError("document tamil quality issue not found")
        return row

    def list_documents(
        self, status: str | None, search: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        clauses, params = [], []
        if status:
            clauses.append("status=?")
            params.append(status)
        if search:
            clauses.append("original_filename LIKE ? ESCAPE '\\'")
            escaped = search.replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM document_sources{where}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM document_sources{where} "
                "ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
        return {
            "items": [decode(row, DOCUMENT_JSON) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    def list_children(
        self, table: str, document_id: int, page: int, page_size: int, *, status: str | None = None
    ) -> dict[str, Any]:
        allowed = {
            "document_pages": (PAGE_JSON, "page_number"),
            "document_candidates": (CANDIDATE_JSON, "sequence_number"),
            "document_processing_jobs": (JOB_JSON, "created_at DESC,id DESC"),
        }
        json_columns, order = allowed[table]
        where, params = "document_source_id=?", [document_id]
        if status:
            column = "extraction_status" if table == "document_pages" else "status"
            where += f" AND {column}=?"
            params.append(status)
        with self.transaction() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {where}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM {table} WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
        return {
            "items": [decode(row, json_columns) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    # --- Phase 4: extraction history (append-only) --------------------------

    def create_extraction(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO document_page_extractions(
            public_id,document_page_id,extraction_method,raw_text,raw_text_hash,ocr_engine,
            ocr_engine_version,ocr_language_mode,ocr_confidence,preprocessing_metadata_json,
            extraction_warnings_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                values["document_page_id"],
                values["extraction_method"],
                values.get("raw_text"),
                values.get("raw_text_hash"),
                values.get("ocr_engine"),
                values.get("ocr_engine_version"),
                values.get("ocr_language_mode"),
                values.get("ocr_confidence"),
                values.get("preprocessing_metadata_json", "{}"),
                values.get("extraction_warnings_json", "[]"),
                values["created_by_admin_public_id"],
            ),
        )
        return public_id

    def list_extractions(
        self, connection: sqlite3.Connection, document_page_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM document_page_extractions WHERE document_page_id=? "
            "ORDER BY created_at DESC, id DESC",
            (document_page_id,),
        ).fetchall()

    # --- Phase 4: page review (mutable status + append-only event log) ------

    def update_page_review(
        self, connection: sqlite3.Connection, page_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE document_pages SET {columns},updated_at=CURRENT_TIMESTAMP WHERE id=?",  # noqa: S608
            (*fields.values(), page_id),
        )

    def add_review_event(self, connection: sqlite3.Connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO document_page_review_events(
            public_id,document_page_id,action,review_status_after,performed_by_admin_public_id,
            notes) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["document_page_id"],
                values["action"],
                values["review_status_after"],
                values["performed_by_admin_public_id"],
                values.get("notes", ""),
            ),
        )
        return public_id

    def list_review_events(
        self, connection: sqlite3.Connection, document_page_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM document_page_review_events WHERE document_page_id=? "
            "ORDER BY created_at DESC, id DESC",
            (document_page_id,),
        ).fetchall()

    # --- Phase 4: repeated elements (mutable suggestion status) --------------

    def create_repeated_element(
        self, connection: sqlite3.Connection, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO document_repeated_elements(
            public_id,document_source_id,normalized_text,element_type,page_occurrences_json,
            confidence) VALUES (?,?,?,?,?,?)""",
            (
                public_id,
                values["document_source_id"],
                values["normalized_text"],
                values["element_type"],
                values.get("page_occurrences_json", "[]"),
                values["confidence"],
            ),
        )
        return public_id

    def repeated_element(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM document_repeated_elements WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("repeated element suggestion not found")
        return row

    def list_repeated_elements(
        self, connection: sqlite3.Connection, document_id: int, *, status: str | None = None
    ) -> list[sqlite3.Row]:
        if status:
            return connection.execute(
                "SELECT * FROM document_repeated_elements WHERE document_source_id=? "
                "AND status=? ORDER BY confidence DESC, id DESC",
                (document_id, status),
            ).fetchall()
        return connection.execute(
            "SELECT * FROM document_repeated_elements WHERE document_source_id=? "
            "ORDER BY confidence DESC, id DESC",
            (document_id,),
        ).fetchall()

    def update_repeated_element(
        self, connection: sqlite3.Connection, element_id: int, fields: dict[str, Any]
    ) -> None:
        if not fields:
            return
        columns = ",".join(f"{key}=?" for key in fields)
        connection.execute(
            f"UPDATE document_repeated_elements SET {columns} WHERE id=?",  # noqa: S608
            (*fields.values(), element_id),
        )

    def clear_repeated_elements(self, connection: sqlite3.Connection, document_id: int) -> None:
        connection.execute(
            "DELETE FROM document_repeated_elements "
            "WHERE document_source_id=? AND status='suggested'",
            (document_id,),
        )
