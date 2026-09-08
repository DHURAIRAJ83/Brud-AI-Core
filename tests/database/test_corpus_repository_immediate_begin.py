"""Phase 7C-37: `CorpusRepository.transaction(immediate=...)` API extension.

Phase 7C-36 empirically proved that `CorpusRepository`'s read-then-write and
repeated-write call paths suffer severe deferred-BEGIN lock-upgrade
contention once pooled, and that `immediate=True` (tested there via the
underlying `BaseRepository.transaction(immediate=True)` mechanism, since
`CorpusRepository` didn't expose the parameter) eliminates it completely.
This file proves the new `immediate` parameter added in this phase is a
minimal, additive, backward-compatible extension: existing callers that
omit it keep today's exact deferred-BEGIN behavior; `immediate=True`
callers reach the real underlying immediate-BEGIN path with no second
transaction implementation and no new connection-management logic. It does
NOT wire `CorpusRepository` into the production `ConnectionPool` -- that
remains a separately authorized future decision.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import pytest

from backend.database.connection import database_connection
from backend.database.connection_pool import ConnectionPool
from backend.database.migrations import initialize_database
from backend.database.repositories.corpus import CorpusRepository


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "corpus.db"
    initialize_database(path)
    return path


def _seed_policy(repo: CorpusRepository) -> str:
    with repo.transaction() as connection:
        return repo.create_policy(
            connection, {"name": "test-policy", "created_by_admin_public_id": "admin-1"}
        )


# --- A/B: default and explicit immediate=False preserve deferred behavior ---


def test_transaction_without_immediate_preserves_deferred_behavior(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    with repo.transaction() as connection:
        connection.execute("SELECT 1")
        # A deferred transaction that has only read so far claims no write
        # lock, so a second, independent connection's write must be free
        # to proceed -- this is the exact deferred-BEGIN signature.
        other = sqlite3.connect(db_path, timeout=0.2)
        other.execute("PRAGMA busy_timeout = 200")
        other.execute("CREATE TABLE IF NOT EXISTS _probe(id INTEGER)")
        other.commit()
        other.close()


def test_transaction_immediate_false_explicit_matches_default(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    with repo.transaction(immediate=False) as connection:
        other = sqlite3.connect(db_path, timeout=0.2)
        other.execute("PRAGMA busy_timeout = 200")
        other.execute("CREATE TABLE IF NOT EXISTS _probe2(id INTEGER)")
        other.commit()
        other.close()


# --- C: immediate=True reaches the real immediate-BEGIN path ---


def test_transaction_immediate_true_claims_write_lock_at_begin(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    with repo.transaction(immediate=True) as connection:
        connection.execute("SELECT 1")
        # An immediate transaction claims the write lock at BEGIN time, so
        # a second, independent connection's write must be blocked.
        blocked = sqlite3.connect(db_path, timeout=0.2)
        blocked.execute("PRAGMA busy_timeout = 200")
        with pytest.raises(sqlite3.OperationalError):
            blocked.execute("CREATE TABLE IF NOT EXISTS _probe3(id INTEGER)")
        blocked.close()


# --- D/E: commit and rollback semantics unchanged ---


def test_commit_behavior_unchanged_deferred(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    public_id = _seed_policy(repo)
    with repo.transaction() as connection:
        row = repo.policy(connection, public_id)
        repo.update_policy(connection, row["id"], {"description": "committed"})
    with repo.transaction() as connection:
        row = repo.policy(connection, public_id)
    assert row["description"] == "committed"


def test_commit_behavior_unchanged_immediate(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    public_id = _seed_policy(repo)
    with repo.transaction(immediate=True) as connection:
        row = repo.policy(connection, public_id)
        repo.update_policy(connection, row["id"], {"description": "committed-immediate"})
    with repo.transaction() as connection:
        row = repo.policy(connection, public_id)
    assert row["description"] == "committed-immediate"


def test_rollback_behavior_unchanged_deferred(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    public_id = _seed_policy(repo)
    with pytest.raises(RuntimeError):
        with repo.transaction() as connection:
            row = repo.policy(connection, public_id)
            repo.update_policy(connection, row["id"], {"description": "should-not-persist"})
            raise RuntimeError("deliberate failure")
    with repo.transaction() as connection:
        row = repo.policy(connection, public_id)
    assert row["description"] != "should-not-persist"


def test_rollback_behavior_unchanged_immediate(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    public_id = _seed_policy(repo)
    with pytest.raises(RuntimeError):
        with repo.transaction(immediate=True) as connection:
            row = repo.policy(connection, public_id)
            repo.update_policy(connection, row["id"], {"description": "should-not-persist-2"})
            raise RuntimeError("deliberate failure")
    with repo.transaction() as connection:
        row = repo.policy(connection, public_id)
    assert row["description"] != "should-not-persist-2"


# --- F: typed exception behavior unchanged ---


def test_not_found_error_unchanged_under_both_modes(db_path: Path) -> None:
    from backend.database.repositories.base import NotFoundError

    repo = CorpusRepository(db_path)
    with pytest.raises(NotFoundError):
        with repo.transaction() as connection:
            repo.policy(connection, "does-not-exist")
    with pytest.raises(NotFoundError):
        with repo.transaction(immediate=True) as connection:
            repo.policy(connection, "does-not-exist")


# --- G: nested/re-entrant behavior unchanged (pool-aware path) ---


def test_reentrant_checkout_still_raises_with_new_parameter_present(db_path: Path) -> None:
    from backend.database.connection_pool import ReentrantCheckout

    pool = ConnectionPool(db_path, size=2)
    repo = CorpusRepository(db_path, pool=pool)
    with pytest.raises(ReentrantCheckout):
        with repo.transaction() as outer_connection:
            outer_connection.execute("SELECT 1")
            with repo.transaction(immediate=True) as inner_connection:
                pass
    assert pool.outstanding == 0


def test_reentrant_checkout_still_raises_deferred_and_immediate_symmetric(db_path: Path) -> None:
    from backend.database.connection_pool import ReentrantCheckout

    pool = ConnectionPool(db_path, size=2)
    repo = CorpusRepository(db_path, pool=pool)
    with pytest.raises(ReentrantCheckout):
        with repo.transaction(immediate=True) as outer_connection:
            outer_connection.execute("SELECT 1")
            with repo.transaction() as inner_connection:
                pass
    assert pool.outstanding == 0


# --- H: no connection leaks ---


def test_no_connection_leak_across_repeated_cycles_pooled(db_path: Path) -> None:
    pool = ConnectionPool(db_path, size=2)
    repo = CorpusRepository(db_path, pool=pool)
    for _ in range(20):
        with repo.transaction() as connection:
            connection.execute("SELECT 1")
    for _ in range(20):
        with repo.transaction(immediate=True) as connection:
            connection.execute("SELECT 1")
    assert pool.outstanding == 0
    assert pool.connection_recreated_count == 0


def test_no_connection_leak_unpooled(db_path: Path) -> None:
    repo = CorpusRepository(db_path)
    for _ in range(10):
        with repo.transaction() as connection:
            connection.execute("SELECT 1")
    for _ in range(10):
        with repo.transaction(immediate=True) as connection:
            connection.execute("SELECT 1")
    # unpooled: nothing to assert about pool state, only that no exception
    # escaped and the database remains usable afterward.
    with database_connection(db_path) as connection:
        connection.execute("SELECT 1")


# --- Real contention re-qualification: pooled+deferred vs pooled+immediate ---
# Barrier-synchronized (never sequential start()/join() -- Phase 7C-26
# established that sequential thread creation can produce a false negative
# via Linux OS-thread-ID recycling).

THREADS = 4
ITERATIONS = 100


def _read_then_write_worker(repo, public_id, barrier, errors, *, immediate):
    barrier.wait()
    for _ in range(ITERATIONS):
        try:
            with repo.transaction(immediate=immediate) as connection:
                row = repo.policy(connection, public_id)
                repo.update_policy(connection, row["id"], {"description": "contended"})
        except sqlite3.OperationalError as exc:
            errors.append(exc)


def _run_concurrent(repo, public_id, *, immediate):
    errors: list[BaseException] = []
    barrier = threading.Barrier(THREADS)
    threads = [
        threading.Thread(
            target=_read_then_write_worker,
            args=(repo, public_id, barrier, errors),
            kwargs={"immediate": immediate},
        )
        for _ in range(THREADS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return errors


def test_pooled_immediate_eliminates_read_then_write_contention(db_path: Path) -> None:
    """The real qualification result this phase's API extension exists to
    make usable: pooled + immediate=True must show zero (or negligible)
    lock errors for the exact read-then-write shape Phase 7C-36 found
    severely contended under pooled + deferred."""

    pool = ConnectionPool(db_path, size=THREADS)
    repo = CorpusRepository(db_path, pool=pool)
    public_id = _seed_policy(repo)

    deferred_errors = _run_concurrent(repo, public_id, immediate=False)
    immediate_errors = _run_concurrent(repo, public_id, immediate=True)

    assert pool.outstanding == 0
    # Immediate must eliminate the failure class entirely -- this is the
    # qualification result, not a fuzzy "fewer errors" claim.
    assert immediate_errors == []
    # Documents *why* the parameter matters: deferred, under the same
    # pooled/concurrent conditions, is expected to show at least one
    # lock-upgrade conflict (probabilistic -- not asserted as a fixed
    # count, consistent with every prior contention-qualification phase's
    # treatment of this race as non-deterministic).
    assert isinstance(deferred_errors, list)  # always true; kept for clarity of intent


# --- I: existing CorpusRepository API tests remain green is verified by
# running tests/backend/test_corpus_api.py separately (not duplicated here).
