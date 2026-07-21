"""Small idempotent migration runner for the Phase 1 SQLite schema."""

import logging
from pathlib import Path

from backend.database.connection import database_connection
from backend.database.schema import INITIAL_SCHEMA, SCHEMA_VERSION

logger = logging.getLogger(__name__)


def initialize_database(database_path: Path) -> int:
    """Create the database and apply all unapplied migrations safely."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    with database_connection(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (SCHEMA_VERSION,)
        ).fetchone()
        if not applied:
            connection.executescript(INITIAL_SCHEMA)
            connection.execute(
                "INSERT INTO schema_migrations(version) VALUES (?)", (SCHEMA_VERSION,)
            )
            logger.info("database_migration_applied", extra={"schema_version": SCHEMA_VERSION})
        else:
            logger.info("database_migration_current", extra={"schema_version": SCHEMA_VERSION})
        connection.commit()
    logger.info("database_initialized", extra={"database_path": str(database_path)})
    return SCHEMA_VERSION
