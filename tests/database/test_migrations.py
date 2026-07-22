from pathlib import Path

from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.schema import SCHEMA_VERSION

REQUIRED_TABLES = {
    "schema_migrations",
    "app_settings",
    "chat_sessions",
    "chat_messages",
    "dataset_sources",
    "dataset_records",
    "training_jobs",
    "model_registry",
    "audit_logs",
}


def test_database_initialization_and_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "test.db"
    assert initialize_database(database_path) == SCHEMA_VERSION
    assert database_path.exists()
    with database_connection(database_path) as connection:
        table_rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in table_rows}
        assert REQUIRED_TABLES <= tables
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_migration_is_idempotent(tmp_path: Path) -> None:
    database_path = tmp_path / "test.db"
    initialize_database(database_path)
    initialize_database(database_path)
    with database_connection(database_path) as connection:
        migrations = connection.execute("SELECT version FROM schema_migrations").fetchall()
        assert [row[0] for row in migrations] == list(range(1, SCHEMA_VERSION + 1))
