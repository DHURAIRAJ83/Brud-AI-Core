from pathlib import Path

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import (
    _apply_v1,
    _apply_v2,
    _apply_v3,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION


def test_upgrade_v3_to_v4_is_additive_and_backed_up(tmp_path: Path) -> None:
    database = tmp_path / "v3.db"
    with database_connection(database) as connection:
        _apply_v1(connection)
        _apply_v2(connection)
        _apply_v3(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved", "manual", "draft", "00000000-0000-0000-0000-000000000044"),
        )
        connection.commit()
    assert current_schema_version(database) == 3
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION and backup is not None and integrity == "ok"
    assert backup.path.is_file() and sha256_file(backup.path) == backup.backup_checksum
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        indexes = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")
        }
        assert {"dataset_import_jobs", "dataset_import_rows", "dataset_import_events"} <= tables
        assert {
            "ix_import_jobs_status",
            "ix_import_rows_hash",
            "ix_import_rows_duplicate",
        } <= indexes
        assert connection.execute("SELECT name FROM dataset_sources").fetchone()[0] == "Preserved"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_fresh_v4_and_idempotency(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
