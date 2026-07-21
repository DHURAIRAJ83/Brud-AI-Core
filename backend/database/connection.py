"""Safe SQLite connection and health helpers."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def connect(database_path: Path) -> sqlite3.Connection:
    """Open a configured SQLite connection with defensive runtime pragmas."""

    connection = sqlite3.connect(database_path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def database_connection(database_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(database_path)
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
