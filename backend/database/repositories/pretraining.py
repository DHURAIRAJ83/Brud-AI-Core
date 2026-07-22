"""Pretraining repository."""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "dataset_version_id",
    "tokenizer_version_id",
    "core_model_version_id",
    "source_checkpoint_id",
    "pretraining_job_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("pretraining row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class PretrainingRepository(BaseRepository):
    def job(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            """SELECT j.*,d.public_id AS dataset_version_public_id,
            t.public_id AS tokenizer_version_public_id,
            m.public_id AS core_model_version_public_id
            FROM pretraining_jobs j
            JOIN dataset_versions d ON d.id=j.dataset_version_id
            JOIN tokenizer_versions t ON t.id=j.tokenizer_version_id
            JOIN core_model_versions m ON m.id=j.core_model_version_id
            WHERE j.public_id=?""",
            (public_id,),
        ).fetchone()
        if not row:
            raise NotFoundError("pretraining job not found")
        return row

    def add_event(
        self,
        connection,
        job_id: int,
        event: str,
        old: str | None,
        new: str | None,
        metadata="{}",
    ) -> None:
        connection.execute(
            """INSERT INTO pretraining_job_events(pretraining_job_id,event_type,
            previous_status,new_status,metadata_json) VALUES (?,?,?,?,?)""",
            (job_id, event, old, new, metadata),
        )
