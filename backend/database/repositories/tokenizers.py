"""Tokenizer registry repository for Phase 7."""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL_KEYS = {
    "id",
    "tokenizer_family_id",
    "dataset_version_id",
    "training_job_id",
    "tokenizer_version_id",
    "tokenizer_evaluation_id",
}


def public_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for key in list(data):
        if key in INTERNAL_KEYS:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class TokenizerRepository(BaseRepository):
    def family(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM tokenizer_families WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("tokenizer family not found")
        return row

    def version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT v.*,f.public_id AS family_public_id,f.name AS family_name,
            d.public_id AS dataset_version_public_id,d.status AS dataset_version_status
            FROM tokenizer_versions v
            JOIN tokenizer_families f ON f.id=v.tokenizer_family_id
            JOIN dataset_versions d ON d.id=v.dataset_version_id
            WHERE v.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("tokenizer version not found")
        return row

    def dataset_version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM dataset_versions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("dataset version not found")
        return row

    def job(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT j.*,v.public_id AS tokenizer_version_public_id
            FROM tokenizer_training_jobs j
            JOIN tokenizer_versions v ON v.id=j.tokenizer_version_id
            WHERE j.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("tokenizer job not found")
        return row

    def add_event(
        self,
        connection: sqlite3.Connection,
        job_id: int,
        event_type: str,
        previous: str | None,
        new: str | None,
        stage: str | None,
        message: str | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        connection.execute(
            """INSERT INTO tokenizer_training_events(training_job_id,event_type,previous_status,
            new_status,stage,message,metadata_json) VALUES (?,?,?,?,?,?,?)""",
            (job_id, event_type, previous, new, stage, message, dumps_json(metadata or {})),
        )

    def list_page(
        self,
        connection: sqlite3.Connection,
        table: str,
        page: int,
        page_size: int,
        order: str = "created_at DESC,id DESC",
    ) -> tuple[list[dict[str, Any]], int]:
        allowed = {
            "tokenizer_families",
            "tokenizer_versions",
            "tokenizer_training_jobs",
            "tokenizer_evaluations",
        }
        if table not in allowed:
            raise ValueError("unsupported tokenizer table")
        total = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        rows = connection.execute(
            f"SELECT * FROM {table} ORDER BY {order} LIMIT ? OFFSET ?",
            (page_size, (page - 1) * page_size),
        ).fetchall()
        return [public_row(row) for row in rows], total
