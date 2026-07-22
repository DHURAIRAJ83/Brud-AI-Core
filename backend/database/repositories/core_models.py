"""Repository for Phase 8 core model metadata."""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "core_model_family_id",
    "config_id",
    "tokenizer_version_id",
    "core_model_version_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("core model row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class CoreModelRepository(BaseRepository):
    def family(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM core_model_families WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("core model family not found")
        return row

    def config(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT c.*,t.public_id AS tokenizer_version_public_id,
            t.vocabulary_size AS tokenizer_vocabulary_size,t.lifecycle_status AS tokenizer_status
            FROM core_model_configs c
            JOIN tokenizer_versions t ON t.id=c.tokenizer_version_id
            WHERE c.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("core model config not found")
        return row

    def version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT v.*,f.public_id AS family_public_id,f.name AS family_name,
            c.public_id AS config_public_id,t.public_id AS tokenizer_version_public_id
            FROM core_model_versions v
            JOIN core_model_families f ON f.id=v.core_model_family_id
            JOIN core_model_configs c ON c.id=v.config_id
            JOIN tokenizer_versions t ON t.id=v.tokenizer_version_id
            WHERE v.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("core model version not found")
        return row

    def tokenizer(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM tokenizer_versions WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("tokenizer version not found")
        return row

    def add_event(
        self,
        connection: sqlite3.Connection,
        version_id: int | None,
        event_type: str,
        previous: str | None,
        new: str | None,
        metadata_json: str = "{}",
    ) -> None:
        connection.execute(
            """INSERT INTO core_model_events(core_model_version_id,event_type,
            previous_status,new_status,metadata_json) VALUES (?,?,?,?,?)""",
            (version_id, event_type, previous, new, metadata_json),
        )
