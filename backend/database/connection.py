"""Safe SQLite connection and health helpers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def connect(
    database_path: Path, *, busy_timeout_ms: int = 5000, wal_enabled: bool = True
) -> sqlite3.Connection:
    """Open a configured SQLite connection with defensive runtime pragmas."""

    connection = sqlite3.connect(database_path, timeout=busy_timeout_ms / 1000)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if wal_enabled:
        connection.execute("PRAGMA journal_mode = WAL")
    connection.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    return connection


@contextmanager
def database_connection(
    database_path: Path, *, busy_timeout_ms: int = 5000, wal_enabled: bool = True
) -> Iterator[sqlite3.Connection]:
    connection = connect(database_path, busy_timeout_ms=busy_timeout_ms, wal_enabled=wal_enabled)
    try:
        yield connection
    finally:
        connection.close()


def database_is_connected(database_path: Path) -> bool:
    """Perform a lightweight database connectivity check."""

    try:
        with database_connection(database_path) as connection:
            return connection.execute("SELECT 1").fetchone()[0] == 1
    except sqlite3.Error:
        return False
