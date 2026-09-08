"""Repository for MB-22: Brud Mini Brain Real Training Execution
Engine.

Five tables, all MB-22's own: `mini_brain_training_jobs`,
`mini_brain_training_checkpoints` (one row per saved checkpoint --
deterministic naming, no overwrite via a unique index on
job+checkpoint_name), `mini_brain_training_metrics` (append-only,
streamed incrementally), `mini_brain_training_events` (append-only),
and `mini_brain_training_engine_memory` (permanent, insert-only). MB-22
never writes to any other system's tables.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, ConflictError, NotFoundError

_JOB_INTERNAL = {"id"}
JOB_JSON_FIELDS = (
    "release_validation_report", "package_validation_report", "authorization_report",
    "resource_plan_report", "training_manifest", "runtime_reservation_report", "training_state",
    "final_report",
)
_CHECKPOINT_INTERNAL = {"id"}
_METRIC_INTERNAL = {"id"}
_MEMORY_INTERNAL = {"id"}


def public_job_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("training job row not found")
    data = dict(row)
    for key in list(data):
        if key in _JOB_INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


def public_checkpoint_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("training checkpoint row not found")
    data = dict(row)
    for key in list(data):
        if key in _CHECKPOINT_INTERNAL or key == "job_id":
            data.pop(key)
        elif key == "is_metadata_only":
            data[key] = bool(data[key])
    return data


def public_metric_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("training metric row not found")
    data = dict(row)
    for key in list(data):
        if key in _METRIC_INTERNAL or key == "job_id":
            data.pop(key)
    return data


def public_memory_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("training engine memory row not found")
    data = dict(row)
    for key in list(data):
        if key in _MEMORY_INTERNAL or key == "job_id":
            data.pop(key)
    return data


class MiniBrainTrainingEngineRepository(BaseRepository):
    # -- jobs ---------------------------------------------------------------

    def create_job(
        self, connection: sqlite3.Connection, *, training_package_session_public_id: str,
        release_governance_session_public_id: str, topic: str, execution_mode: str,
        created_by_admin_public_id: str, core_model_version_public_id: str | None = None,
        dataset_version_public_id: str | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_training_jobs(
                public_id, training_package_session_public_id, release_governance_session_public_id,
                topic, execution_mode, created_by_admin_public_id, core_model_version_public_id,
                dataset_version_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, training_package_session_public_id, release_governance_session_public_id,
                topic, execution_mode, created_by_admin_public_id, core_model_version_public_id,
                dataset_version_public_id,
            ),
        )
        return public_id

    def dataset_version(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row | None:
        """Phase 2.7F: read-only lookup against `dataset_versions` -- a
        table MB-22 does not own, but reading it to validate a real,
        admin-supplied dataset identity is a different, safe category from
        the write-service imports (`DatasetService`) MB-22's own service
        file is forbidden from ever using."""
        return connection.execute(
            "SELECT * FROM dataset_versions WHERE public_id=?", (public_id,)
        ).fetchone()

    def get_job(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_training_jobs WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"training job not found: {public_id}")
        return row

    def list_jobs(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_training_jobs ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    def update_job(
        self, connection: sqlite3.Connection, public_id: str, fields: dict[str, Any],
        *, expected_status: str | tuple[str, ...] | None = None,
    ) -> sqlite3.Row:
        """Phase 2.8F: `expected_status`, when given, turns this write
        into a real, atomic compare-and-swap -- `AND status IN (...)` is
        added to the WHERE clause of the single `UPDATE` statement
        itself, so SQLite (not application code) is what actually
        decides whether the job's status still matches what the caller
        observed before doing its (possibly expensive) work. If another
        process already changed the status in the meantime, this
        `UPDATE` affects zero rows and `ConflictError` is raised --
        never a silent, stale write. This is the minimal fix for the
        exact multi-process race Phase 2.8F reproduced directly: two
        independent OS processes both reading `status='paused'` (or
        `'running'`) before either commits, then both writing as if
        their own stale read were still true. A plain (non-CAS) call
        with `expected_status=None` is byte-for-byte the original,
        unconditional `UPDATE ... WHERE public_id=?` every pre-2.8F
        caller already relied on."""

        self.get_job(connection, public_id)
        set_clauses = []
        values: list[Any] = []
        json_columns = {f"{f}_json" for f in JOB_JSON_FIELDS}
        for column, value in fields.items():
            set_clauses.append(f'"{column}"=?')
            values.append(dumps_json(value) if column in json_columns else value)
        set_clauses.append('"updated_at"=CURRENT_TIMESTAMP')
        values.append(public_id)
        where = 'public_id=?'
        if expected_status is not None:
            statuses = (expected_status,) if isinstance(expected_status, str) else tuple(expected_status)
            where += f' AND status IN ({",".join("?" for _ in statuses)})'
            values.extend(statuses)
        cursor = connection.execute(
            f'UPDATE mini_brain_training_jobs SET {", ".join(set_clauses)} WHERE {where}',
            values,
        )
        if expected_status is not None and cursor.rowcount == 0:
            raise ConflictError(
                f"job {public_id} status changed concurrently -- no longer "
                f"{'/'.join(statuses)}, cannot apply this update"
            )
        return self.get_job(connection, public_id)

    # -- checkpoints ----------------------------------------------------------

    def create_checkpoint(
        self, connection: sqlite3.Connection, *, job_id: int, step: int, epoch: int, checkpoint_name: str,
        relative_path: str, sha256: str, file_size_bytes: int, is_metadata_only: bool,
        core_model_version_public_id: str | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_training_checkpoints(
                public_id, job_id, step, epoch, checkpoint_name, relative_path, sha256,
                file_size_bytes, is_metadata_only, core_model_version_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, job_id, step, epoch, checkpoint_name, relative_path, sha256,
                file_size_bytes, int(is_metadata_only), core_model_version_public_id,
            ),
        )
        return public_id

    def list_checkpoints(
        self, connection: sqlite3.Connection, *, job_id: int,
    ) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM mini_brain_training_checkpoints WHERE job_id=? ORDER BY step",
            (job_id,),
        ).fetchall()

    def get_checkpoint(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM mini_brain_training_checkpoints WHERE public_id=?", (public_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"training checkpoint not found: {public_id}")
        return row

    def mark_checkpoint_registered(
        self, connection: sqlite3.Connection, checkpoint_id: int, pretraining_checkpoint_public_id: str,
    ) -> None:
        connection.execute(
            """UPDATE mini_brain_training_checkpoints SET pretraining_checkpoint_public_id=?
            WHERE id=?""",
            (pretraining_checkpoint_public_id, checkpoint_id),
        )

    # -- metrics (append-only) -------------------------------------------------

    def append_metric(
        self, connection: sqlite3.Connection, *, job_id: int, step: int, epoch: int, loss: float | None,
        learning_rate: float | None, tokens_per_second: float | None, examples_per_second: float | None,
        gpu_memory_mb: float | None, cpu_memory_mb: float | None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_training_metrics(
                public_id, job_id, step, epoch, loss, learning_rate, tokens_per_second,
                examples_per_second, gpu_memory_mb, cpu_memory_mb
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, job_id, step, epoch, loss, learning_rate, tokens_per_second,
                examples_per_second, gpu_memory_mb, cpu_memory_mb,
            ),
        )
        return public_id

    def list_metrics(
        self, connection: sqlite3.Connection, *, job_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_training_metrics WHERE job_id=? ORDER BY step LIMIT ? OFFSET ?",
            (job_id, limit, offset),
        ).fetchall()

    # -- training engine memory (permanent, insert-only) -----------------------

    def create_memory(
        self, connection: sqlite3.Connection, *, job_id: int, topic: str, execution_mode: str,
        final_status: str, total_steps: int, final_loss: float | None, best_loss: float | None,
        checkpoint_count: int, recorded_by_admin_public_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_training_engine_memory(
                public_id, job_id, topic, execution_mode, final_status, total_steps, final_loss,
                best_loss, checkpoint_count, recorded_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                public_id, job_id, topic, execution_mode, final_status, total_steps, final_loss,
                best_loss, checkpoint_count, recorded_by_admin_public_id,
            ),
        )
        return public_id

    def list_memory(
        self, connection: sqlite3.Connection, *, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            "SELECT * FROM mini_brain_training_engine_memory ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()

    # -- events (append-only) ---------------------------------------------------

    def create_event(
        self, connection: sqlite3.Connection, *, job_id: int, event_type: str,
        stage: str | None = None, message: str = "", metadata: dict[str, Any] | None = None,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO mini_brain_training_events(
                public_id, job_id, event_type, stage, message, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (public_id, job_id, event_type, stage, message, dumps_json(metadata or {})),
        )
        return public_id

    def list_events(
        self, connection: sqlite3.Connection, *, job_id: int, limit: int, offset: int,
    ) -> list[sqlite3.Row]:
        limit, offset = self.pagination(limit, offset)
        return connection.execute(
            """SELECT * FROM mini_brain_training_events WHERE job_id=?
            ORDER BY id DESC LIMIT ? OFFSET ?""",
            (job_id, limit, offset),
        ).fetchall()


__all__ = [
    "MiniBrainTrainingEngineRepository", "public_job_row", "public_checkpoint_row", "public_metric_row",
    "public_memory_row", "JOB_JSON_FIELDS",
]
