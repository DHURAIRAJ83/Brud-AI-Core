from pathlib import Path

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import (
    _apply_v1,
    _apply_v2,
    current_schema_version,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION


def test_upgrade_v2_to_current_preserves_dataset_data_and_creates_auth_tables(
    tmp_path: Path,
) -> None:
    database = tmp_path / "phase2.db"
    with database_connection(database) as connection:
        _apply_v1(connection)
        _apply_v2(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved", "manual", "draft", "00000000-0000-0000-0000-000000000001"),
        )
        connection.commit()
    assert current_schema_version(database) == 2
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION and backup is not None and integrity == "ok"
    with database_connection(database) as connection:
        assert connection.execute("SELECT name FROM dataset_sources").fetchone()[0] == "Preserved"
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"admin_accounts", "admin_sessions"} <= tables
