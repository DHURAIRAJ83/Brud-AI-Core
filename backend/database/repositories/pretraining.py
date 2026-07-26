"""Pretraining repository."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
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
    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        """Defaults to `immediate=True`: the pretraining worker writes a
        metric and/or checkpoint row on every training step (as often as
        every step, depending on configuration) while the API layer polls
        job/metrics status and pause/resume flags on the same database from
        another thread. Every one of this repository's transactions reads
        the current job row and then conditionally writes -- the exact
        shape that a deferred `BEGIN` leaves vulnerable to a lock-upgrade
        failure under that concurrent write load (see
        `BaseRepository.transaction`). None of this repository's callers in
        `PretrainingService` nest a second `transaction()` inside an
        already-open one, so there is no deadlock risk in claiming the
        write lock up front here.
        """
        with super().transaction(immediate=immediate) as connection:
            yield connection

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
