"""Parameterized persistence and safe public projections for documents."""

import math
import sqlite3
from typing import Any

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

DOCUMENT_JSON = {"metadata_json"}
PAGE_JSON = {"warnings_json"}
JOB_JSON = {"selected_pages_json", "configuration_json"}
CANDIDATE_JSON = {"metadata_json", "validation_errors_json", "validation_warnings_json"}


def decode(row: sqlite3.Row, json_columns: set[str], internal: bool = False) -> dict[str, Any]:
    value = dict(row)
    for column in json_columns:
        if column in value:
            default = (
                [] if any(token in column for token in ("warnings", "errors", "pages")) else {}
            )
            value[column.removesuffix("_json")] = loads_json(value.pop(column), default=default)
    if not internal:
        for key in ("id", "document_source_id", "processing_job_id", "stored_filename"):
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
