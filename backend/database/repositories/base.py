"""Shared repository safety primitives."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from backend.database.connection import database_connection

if TYPE_CHECKING:
    from backend.database.connection_pool import ConnectionPool


class RepositoryError(RuntimeError):
    """Controlled base exception for persistence failures."""


class NotFoundError(RepositoryError):
    """Requested public entity does not exist."""


class ConflictError(RepositoryError):
    """Requested change conflicts with an existing entity or immutable state."""


class ValidationError(RepositoryError):
    """Requested repository operation violates a lifecycle rule."""


class BaseRepository:
    def __init__(self, database_path: Path, *, pool: "ConnectionPool | None" = None) -> None:
        self.database_path = database_path
        self.pool = pool

    @contextmanager
    def _acquire_connection(self) -> Iterator[sqlite3.Connection]:
        """Phase 7C-28: the sole seam between `transaction()`'s BEGIN/COMMIT/
        ROLLBACK/exception logic (unchanged below) and how a connection is
        obtained. `pool` defaults to `None` for every existing caller, so
        every one of the ~1,926 pre-existing `SomeRepository(database_path)`
        construction sites is byte-for-byte behavior-unchanged: they keep
        opening a fresh connection via `database_connection()` and closing
        it, exactly as before this phase. Passing `pool=` at repository
        construction time (not per `transaction()` call, and not via a
        hidden global) is an explicit, request-scoped, per-repository
        opt-in -- no mass call-site modification, no ambiguity about which
        pool a given repository instance uses, no implicit pool creation."""

        if self.pool is not None:
            connection = self.pool.checkout()
            try:
                yield connection
            finally:
                self.pool.checkin(connection)
        else:
            with database_connection(self.database_path) as connection:
                yield connection

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

        Connection acquisition itself (fresh `database_connection()` vs. a
        pooled `ConnectionPool` checkout) is controlled entirely by
        `self.pool` -- see `_acquire_connection()`. This method's own
        BEGIN/COMMIT/ROLLBACK/exception semantics are identical either way;
        Phase 7C-28 qualified this equivalence directly (real concurrent
        multi-threaded integration test, real nested-propagation
        compatibility test, real ReentrantCheckout test) before this
        parameter existed.
        """
        with self._acquire_connection() as connection:
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
