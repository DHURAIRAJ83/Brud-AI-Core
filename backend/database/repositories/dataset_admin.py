"""Explicit SQL operations for Phase 3 dataset administration."""

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError


def public_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for key in list(data):
        if key in {"id", "source_id", "dataset_record_id"}:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class DatasetAdminRepository(BaseRepository):
    def source_by_public_id(self, connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM dataset_sources WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("dataset source not found")
        return row

    def create_source(self, connection, values: dict[str, Any]) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO dataset_sources(name,source_type,status,public_id,language,
            licence_name,licence_status,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
            (
                values["name"],
                "manual",
                "draft",
                public_id,
                values["language"],
                values.get("licence_name"),
                values["licence_status"],
                dumps_json(values["metadata"]),
            ),
        )
        return public_id

    def list_sources(self, filters: dict[str, Any], page: int, page_size: int) -> tuple[list, int]:
        clauses, params = [], []
        for column in ("status", "language", "source_type", "licence_status"):
            if filters.get(column):
                clauses.append(f"{column}=?")
                params.append(filters[column])
        if filters.get("search"):
            clauses.append("name LIKE ? ESCAPE '\\'")
            escaped = filters["search"].replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{escaped}%")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.transaction() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM dataset_sources{where}", params
            ).fetchone()[0]
            rows = connection.execute(
                f"SELECT * FROM dataset_sources{where} "
                "ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
        return [public_row(row) for row in rows], total

    def record_by_public_id(self, connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT r.*,s.public_id AS source_public_id,s.name AS source_name
            FROM dataset_records r LEFT JOIN dataset_sources s ON s.id=r.source_id
            WHERE r.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("dataset record not found")
        return row

    def list_records(self, filters: dict[str, Any], page: int, page_size: int) -> tuple[list, int]:
        clauses, params = [], []
        mapping = {
            "status": "r.status",
            "language": "r.language",
            "record_type": "r.record_type",
            "source": "s.public_id",
        }
        for key, column in mapping.items():
            if filters.get(key):
                clauses.append(f"{column}=?")
                params.append(filters[key])
        if filters.get("search"):
            escaped = filters["search"].replace("%", "\\%").replace("_", "\\_")
            clauses.append(
                "(r.instruction LIKE ? ESCAPE '\\' OR r.input_text LIKE ? ESCAPE '\\' "
                "OR r.output_text LIKE ? ESCAPE '\\')"
            )
            params.extend([f"%{escaped}%"] * 3)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        base = " FROM dataset_records r LEFT JOIN dataset_sources s ON s.id=r.source_id"
        with self.transaction() as connection:
            total = connection.execute(f"SELECT COUNT(*){base}{where}", params).fetchone()[0]
            rows = connection.execute(
                f"SELECT r.*,s.public_id AS source_public_id,s.name AS source_name{base}{where} "
                "ORDER BY r.created_at DESC,r.id DESC LIMIT ? OFFSET ?",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
        return [public_row(row) for row in rows], total

    def duplicate(self, connection, content_hash: str, exclude: str | None = None):
        sql = "SELECT public_id,status FROM dataset_records WHERE content_hash=?"
        params: list[Any] = [content_hash]
        if exclude:
            sql += " AND public_id<>?"
            params.append(exclude)
        return connection.execute(sql, params).fetchone()
