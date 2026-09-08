"""Minimal, real, production-capable SQLite connection pool with a
re-entrancy guard.

Phase 7C-24 attempted to implement only the `ReentrantCheckout` guard
qualified in Phase 7C-18 and correctly stopped: no connection pool existed
anywhere in the codebase for a checkout/checkin guard to attach to (the
guard's Phase 7C-18 design was validated only against a disposable synthetic
mini-pool in a throwaway prototype script, never against real production
code). Phase 7C-25 closes that sequencing gap by giving the guard a real,
importable home: this module originally wrapped
`backend.database.connection.connect()` directly, using the exact same
pragmas/defaults as every other connection in the codebase (Phase 7C-27
changed *how* the connection is constructed -- see below -- but not the
pragma values, so a `checkout()`ed connection remains functionally
indistinguishable from one obtained any other way).

Scope boundary (deliberate, not an oversight): this module is NOT wired
into `BaseRepository.transaction()`, FastAPI startup, or any live request
path in this phase. Every one of the ~1,900 existing `transaction()` call
sites keeps opening its own fresh, independent connection exactly as
before. This pool exists as real, tested, production-quality code that the
already-authorized `connection=` propagation idiom (Phase 7C-16
`create_turn`, Phase 7C-20 `processor_for_version`, Phase 7C-22
`evaluate_suitability`) can be exercised against -- proving the guard is a
genuine production implementation rather than an unwired design artifact --
without that amounting to a production pooling rollout, which remains a
separately authorized, future decision.

Phase 7C-27 fix: pooled connections must be usable by whichever thread
checks them out over their *lifetime*, not just the thread that created
them -- that is the entire point of pooling. `backend.database.connection
.connect()` never passes `check_same_thread=False` (correctly so: it is
shared by ~1,926 other call sites that each use one connection on one
thread for one short-lived transaction, so the default `True` is the
right, defensive choice for all of them). This module therefore does NOT
call the shared `connect()` -- it builds its own connections directly via
`sqlite3.connect(..., check_same_thread=False)`, duplicating the same
three defensive pragmas `connect()` sets, so a pooled connection is
functionally identical to one produced by `connect()` except for the one
attribute that must differ for pooling to be possible at all. Before this
fix, every genuinely cross-thread checkout/checkin silently tripped
`_is_healthy()`'s `SELECT 1` into a `sqlite3.ProgrammingError`
(`check_same_thread` violation), which `_is_healthy()` converts into a
plain `False` -- so the connection was silently discarded and a fresh one
created on *every* cross-thread checkout, defeating pooling with no
observable signal. Confirmed empirically (Phase 7C-26 audit, reproduced
again in Phase 7C-27 with genuinely concurrent, Barrier-synchronized
threads -- sequential `start()`/`join()` pairs give a false negative here,
since Linux can recycle OS thread ids once a thread exits, which
accidentally satisfies `check_same_thread` even across logically distinct
threads).
"""

from __future__ import annotations

import queue
import sqlite3
import threading
from pathlib import Path


class PoolExhausted(RuntimeError):
    """Raised when `checkout()` times out waiting for an available
    connection because the pool is fully checked out."""


class ReentrantCheckout(RuntimeError):
    """Raised immediately -- before any pool wait, before any second SQLite
    connection is acquired, and before any SQLite lock/busy_timeout wait
    can occur -- when the calling thread already owns a checked-out
    connection and attempts a second `checkout()` on the same call path.

    This is the Phase 7C-18-qualified re-entrancy invariant: "A logical
    execution context that already owns a checked-out connection must not
    silently acquire a second connection for a nested database operation on
    the same call path." The fix is always the same one already proven at
    every real nested chain found in this investigation (Phase 7C-16
    `create_turn`, Phase 7C-20 `processor_for_version`, Phase 7C-22
    `evaluate_suitability`): thread the existing connection through
    explicitly via `connection=...` instead of checking out a second one.
    """


class ConnectionPool:
    """Bounded pool of real SQLite connections with thread-local
    re-entrancy guarding.

    Deliberately minimal: no capacity tuning, no throughput optimization,
    no WAL policy change -- `size`/`busy_timeout_ms`/`wal_enabled` use the
    exact same defaults as `backend.database.connection.connect()`.
    """

    def __init__(
        self,
        database_path: Path,
        *,
        size: int = 4,
        busy_timeout_ms: int = 5000,
        wal_enabled: bool = True,
        checkout_timeout_s: float = 5.0,
    ) -> None:
        if size < 1:
            raise ValueError("size must be at least 1")
        self._database_path = database_path
        self._busy_timeout_ms = busy_timeout_ms
        self._wal_enabled = wal_enabled
        self._checkout_timeout_s = checkout_timeout_s
        self._size = size
        self._local = threading.local()
        self._accounting_lock = threading.Lock()
        self._outstanding = 0
        self._reused_count = 0
        self._recreated_count = 0
        self._available: queue.Queue[sqlite3.Connection] = queue.Queue()
        for _ in range(size):
            self._available.put(self._new_connection())

    def _new_connection(self) -> sqlite3.Connection:
        """Builds a connection directly (not via the shared `connect()`)
        so it can be marked `check_same_thread=False` -- required for a
        pooled connection to be safely handed to a different thread than
        the one that created it, without weakening the shared `connect()`
        default for its ~1,926 other, non-pooled callers."""

        connection = sqlite3.connect(
            self._database_path,
            timeout=self._busy_timeout_ms / 1000,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if self._wal_enabled:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout_ms)}")
        return connection

    @staticmethod
    def _is_healthy(connection: sqlite3.Connection) -> bool:
        try:
            connection.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def checkout(self) -> sqlite3.Connection:
        """Returns a real connection, owned by the calling thread until
        `checkin()` is called. Raises `ReentrantCheckout` immediately if
        the calling thread already owns one -- no pool wait, no SQLite I/O,
        no second connection created."""

        if getattr(self._local, "owned_connection", None) is not None:
            raise ReentrantCheckout(
                "this thread already owns a checked-out connection; pass "
                "connection=<existing connection> explicitly to the nested "
                "call instead of checking out a second one"
            )

        try:
            connection = self._available.get(timeout=self._checkout_timeout_s)
        except queue.Empty:
            raise PoolExhausted(
                f"no connection became available within {self._checkout_timeout_s}s "
                f"(pool size={self._size}, outstanding={self.outstanding})"
            ) from None

        if self._is_healthy(connection):
            with self._accounting_lock:
                self._reused_count += 1
        else:
            self._discard(connection)
            connection = self._new_connection()
            with self._accounting_lock:
                self._recreated_count += 1

        with self._accounting_lock:
            self._outstanding += 1
        self._local.owned_connection = connection
        return connection

    def checkin(self, connection: sqlite3.Connection) -> None:
        """Returns a connection to the pool and clears this thread's
        ownership. Safe to call from an `except`/`finally` block. Raises if
        the calling thread does not currently own exactly this connection
        (guards against double-checkin and cross-thread misuse)."""

        owned = getattr(self._local, "owned_connection", None)
        if owned is None:
            raise RuntimeError(
                "checkin() called but this thread does not currently own a "
                "checked-out connection (already returned, or never checked out)"
            )
        if owned is not connection:
            raise RuntimeError(
                "checkin() called with a connection this thread did not "
                "check out from this pool"
            )

        self._local.owned_connection = None
        with self._accounting_lock:
            self._outstanding -= 1

        if not self._is_healthy(connection):
            self._discard(connection)
            connection = self._new_connection()
            with self._accounting_lock:
                self._recreated_count += 1
        self._available.put(connection)

    @staticmethod
    def _discard(connection: sqlite3.Connection) -> None:
        try:
            connection.close()
        except sqlite3.Error:
            pass

    def checkout_scope(self) -> "_PoolScope":
        """Context manager: `checkout()` on enter, `checkin()` on exit --
        including on exception -- the standard way application code should
        use the pool."""

        return _PoolScope(self)

    @property
    def outstanding(self) -> int:
        with self._accounting_lock:
            return self._outstanding

    @property
    def connection_reused_count(self) -> int:
        """Number of `checkout()` calls that returned an already-existing,
        still-healthy connection rather than creating a new one. The
        Phase 7C-27 fix is exactly what makes this counter meaningfully
        greater than zero across genuinely concurrent, cross-thread
        checkout traffic -- before the fix, every cross-thread checkout
        fell through to `connection_recreated_count` instead."""

        with self._accounting_lock:
            return self._reused_count

    @property
    def connection_recreated_count(self) -> int:
        """Number of times `checkout()`/`checkin()` discarded a connection
        that failed its `SELECT 1` health check and created a replacement.
        Distinct from `connection_reused_count`: this reflects genuine
        broken-connection replacement (or, before the Phase 7C-27 fix, the
        silent-defeat failure mode where every cross-thread checkout was
        misdiagnosed as \"broken\")."""

        with self._accounting_lock:
            return self._recreated_count

    def owns_connection(self) -> bool:
        """True if the calling thread currently owns a checked-out
        connection from this pool."""

        return getattr(self._local, "owned_connection", None) is not None

    def close(self) -> None:
        """Closes every idle connection currently sitting in the pool.
        Does not affect connections currently checked out by any thread."""

        while True:
            try:
                connection = self._available.get_nowait()
            except queue.Empty:
                break
            self._discard(connection)


class _PoolScope:
    def __init__(self, pool: ConnectionPool) -> None:
        self._pool = pool
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._connection = self._pool.checkout()
        return self._connection

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._connection is not None:
            connection, self._connection = self._connection, None
            self._pool.checkin(connection)


__all__ = ["ConnectionPool", "PoolExhausted", "ReentrantCheckout"]
