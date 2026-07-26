"""Shared repository safety primitives."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from backend.database.connection import database_connection


class RepositoryError(RuntimeError):
    """Controlled base exception for persistence failures."""


class NotFoundError(RepositoryError):
    """Requested public entity does not exist."""


class ConflictError(RepositoryError):
    """Requested change conflicts with an existing entity or immutable state."""


class ValidationError(RepositoryError):
    """Requested repository operation violates a lifecycle rule."""


class BaseRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @contextmanager
    def transaction(self, *, immediate: bool = False) -> Iterator[sqlite3.Connection]:
        """`immediate=True` claims the write lock at BEGIN time instead of
        deferring it until the transaction's first write statement. A
        deferred transaction that reads, then later writes, can find its
        read snapshot invalidated by a concurrent writer's commit in
        between -- SQLite raises `sqlite3.OperationalError: database is
        locked` for that lock upgrade, and `busy_timeout` does not retry it
        (it's a lock-upgrade/snapshot conflict, not a plain contended wait).
        Reproduced directly against concurrent read-then-write connections
        under write-heavy load (e.g. the pretraining worker's per-step
        checkpoint/metric writes racing the admin session touch on every
        request).

        Defaults to False (today's plain `BEGIN`) because some call sites
        open a second, independent connection via a nested repository/
        service call while an outer `transaction()` on a first connection
        is still open (e.g. `_processor_for_experiment` inside
        `generate_profile`); if both connections claimed the write lock
        immediately, the second would deadlock behind the first with no
        thread able to release it. Only opt into `immediate=True` at (or
        for) callers verified not to nest a second `transaction()` inside
        an already-open one.
        """
        with database_connection(self.database_path) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
                yield connection
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise ConflictError(str(exc)) from exc
            except ValidationError:
                connection.rollback()
                columns = {row[1] for row in connection.execute("PRAGMA table_info(audit_logs)")}
                if "public_id" in columns:
                    connection.execute(
                        """INSERT INTO audit_logs(action,actor,details,public_id,event_type,
                        actor_type,outcome,metadata_json) VALUES (?,?,?,?,?,?,?,?)""",
                        (
                            "repository_validation_failure",
                            "system",
                            "{}",
                            str(uuid4()),
                            "repository_validation_failure",
                            "system",
                            "warning",
                            "{}",
                        ),
                    )
                    connection.commit()
                raise
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def pagination(limit: int, offset: int) -> tuple[int, int]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValidationError("limit must be 1..100 and offset must be non-negative")
        return limit, offset
