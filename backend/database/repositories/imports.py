"""Explicit parameterized persistence for registered dataset-import jobs."""

import math
import sqlite3
from typing import Any

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

JOB_JSON_COLUMNS = {"field_mapping_json", "parser_options_json"}
ROW_JSON_COLUMNS = {
    "raw_data_json",
    "normalized_data_json",
    "metadata_json",
    "validation_errors_json",
    "validation_warnings_json",
}


def _decode(row: sqlite3.Row, json_columns: set[str], *, internal: bool = False) -> dict[str, Any]:
    value = dict(row)
    for column in json_columns:
        if column in value:
            value[column.removesuffix("_json")] = loads_json(
                value.pop(column), default=[] if "errors" in column or "warnings" in column else {}
            )
    if not internal:
        value.pop("id", None)
        value.pop("import_job_id", None)
        value.pop("stored_filename", None)
    return value


class ImportRepository(BaseRepository):
    def job(self, connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM dataset_import_jobs WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("dataset import job not found")
        return row

    def public_job(self, row: sqlite3.Row) -> dict[str, Any]:
        return _decode(row, JOB_JSON_COLUMNS)

    def internal_job(self, row: sqlite3.Row) -> dict[str, Any]:
        return _decode(row, JOB_JSON_COLUMNS, internal=True)

    def list_jobs(
        self,
        *,
        status: str | None,
        file_type: str | None,
        search: str | None,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if file_type:
            clauses.append("detected_file_type=?")
            params.append(file_type)
        if search:
            escaped = search.replace("%", "\\%").replace("_", "\\_")
            clauses.append("original_filename LIKE ? ESCAPE '\\'")
            params.append(f"%{escaped}%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM dataset_import_jobs{where}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM dataset_import_jobs{where} ORDER BY created_at DESC,id DESC "
                "LIMIT ? OFFSET ?",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
        return {
            "items": [self.public_job(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    def list_rows(
        self, job_id: int, row_status: str | None, page: int, page_size: int
    ) -> dict[str, Any]:
        where = " WHERE import_job_id=?"
        params: list[Any] = [job_id]
        if row_status:
            where += " AND row_status=?"
            params.append(row_status)
        with self.transaction() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM dataset_import_rows{where}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM dataset_import_rows{where} ORDER BY row_number LIMIT ? OFFSET ?",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
        items = [_decode(row, ROW_JSON_COLUMNS) for row in rows]
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    def events(self, job_id: int) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            rows = connection.execute(
                """SELECT event_type,previous_status,new_status,message,metadata_json,created_at
                FROM dataset_import_events WHERE import_job_id=? ORDER BY id""",
                (job_id,),
            ).fetchall()
        return [_decode(row, {"metadata_json"}) for row in rows]
