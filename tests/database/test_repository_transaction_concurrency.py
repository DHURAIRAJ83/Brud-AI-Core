"""Regression coverage for the pretraining pause/resume flakiness: a
read-then-write transaction opened with a plain, deferred `BEGIN` can find
its read snapshot invalidated by a concurrent writer's commit before its own
later write executes. SQLite raises `sqlite3.OperationalError: database is
locked` for that lock-upgrade failure, and `busy_timeout` does not retry it
(it's a snapshot conflict, not a plain contended wait) -- reproduced
directly below. `transaction(immediate=True)` claims the write lock at BEGIN
time instead, so the busy handler can actually do its job.

This exercises the same read-then-write-under-contention shape that the
pretraining worker's per-step checkpoint/metric writes and the admin
session's request-time touch produce, but directly against the shared
repository primitive and without the slow model/tokenizer machinery, so it
runs in well under a second and can be looped many times for confidence.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from backend.database.connection import database_connection
from backend.database.repositories.base import BaseRepository
from backend.database.repositories.pretraining import PretrainingRepository

THREADS = 4
ITERATIONS_PER_THREAD = 150


@pytest.fixture
def counter_db(tmp_path: Path) -> Path:
    database_path = tmp_path / "concurrency.db"
    with database_connection(database_path) as connection:
        connection.execute("CREATE TABLE counter(id INTEGER PRIMARY KEY, value INTEGER NOT NULL)")
        connection.execute("INSERT INTO counter(id, value) VALUES (1, 0)")
        connection.commit()
    return database_path


def _read_then_increment(
    repository: BaseRepository, errors: list[BaseException], *, immediate: bool
) -> None:
    for _ in range(ITERATIONS_PER_THREAD):
        try:
            with repository.transaction(immediate=immediate) as connection:
                current = connection.execute(
                    "SELECT value FROM counter WHERE id=1"
                ).fetchone()["value"]
                connection.execute("UPDATE counter SET value=? WHERE id=1", (current + 1,))
        except sqlite3.OperationalError as exc:  # pragma: no cover - failure path
            errors.append(exc)


def _run_concurrent_increments(
    repository: BaseRepository, *, immediate: bool
) -> list[BaseException]:
    errors: list[BaseException] = []
    threads = [
        threading.Thread(
            target=_read_then_increment, args=(repository, errors), kwargs={"immediate": immediate}
        )
        for _ in range(THREADS)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return errors


def test_immediate_transactions_never_hit_database_locked_under_contention(
    counter_db: Path,
) -> None:
    repository = BaseRepository(counter_db)
    errors = _run_concurrent_increments(repository, immediate=True)

    assert errors == []
    with database_connection(counter_db) as connection:
        final_value = connection.execute("SELECT value FROM counter WHERE id=1").fetchone()["value"]
    # No lost updates either: BEGIN IMMEDIATE serializes the read-modify-write
    # cycle across threads, so every increment is durably reflected.
    assert final_value == THREADS * ITERATIONS_PER_THREAD


def test_deferred_transactions_can_hit_database_locked_under_the_same_contention(
    counter_db: Path,
) -> None:
    """Documents *why* immediate=True is opt-in rather than the default:
    this is the failure this fix targets, reproduced directly against the
    shared primitive rather than inferred from a flaky end-to-end test."""

    repository = BaseRepository(counter_db)
    errors = _run_concurrent_increments(repository, immediate=False)

    assert any(isinstance(exc, sqlite3.OperationalError) for exc in errors), (
        "expected the deferred-BEGIN race to reproduce at least one "
        "'database is locked' error under this contention -- if this "
        "assertion now fails, the reproduction shape itself may need "
        "revisiting rather than treating it as a spurious pass"
    )


def test_base_repository_transaction_defaults_to_deferred(counter_db: Path) -> None:
    """Locks in that plain `transaction()` (used by every other repository,
    including ones that nest a second connection's transaction() inside an
    already-open one) keeps today's deferred BEGIN unless a caller
    explicitly opts into immediate=True."""

    repository = BaseRepository(counter_db)
    with repository.transaction() as connection:
        connection.execute("SELECT value FROM counter WHERE id=1")
        other = sqlite3.connect(counter_db, timeout=0.2)
        other.execute("PRAGMA busy_timeout = 200")
        # A deferred transaction that has only read so far claims no write
        # lock, so a second connection's write must be free to proceed.
        other.execute("UPDATE counter SET value=99 WHERE id=1")
        other.commit()
        other.close()


def test_pretraining_repository_transaction_defaults_to_immediate(counter_db: Path) -> None:
    """`PretrainingRepository` overrides the default to immediate=True: its
    callers in `PretrainingService` never nest a second `transaction()`
    inside an already-open one, and it is exactly the repository under
    write-heavy contention during pause/resume."""

    repository = PretrainingRepository(counter_db)
    with repository.transaction() as connection:
        connection.execute("SELECT value FROM counter WHERE id=1")
        blocked = sqlite3.connect(counter_db, timeout=0.2)
        blocked.execute("PRAGMA busy_timeout = 200")
        with pytest.raises(sqlite3.OperationalError):
            blocked.execute("UPDATE counter SET value=99 WHERE id=1")
        blocked.close()
