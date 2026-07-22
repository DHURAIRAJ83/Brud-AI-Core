from pathlib import Path

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import (
    _apply_v1,
    _apply_v2,
    _apply_v3,
    _apply_v4,
    _apply_v5,
    _apply_v6,
    _apply_v7,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION


def test_upgrade_v7_to_v8_is_additive_verified_and_backed_up(tmp_path: Path) -> None:
    database = tmp_path / "v7.db"
    with database_connection(database) as connection:
        _apply_v1(connection)
        _apply_v2(connection)
        _apply_v3(connection)
        _apply_v4(connection)
        _apply_v5(connection)
        _apply_v6(connection)
        _apply_v7(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved", "manual", "draft", "00000000-0000-0000-0000-000000000088"),
        )
        connection.commit()
    assert current_schema_version(database) == 7
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
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
        triggers = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")
        }
        assert {
            "core_model_families",
            "core_model_configs",
            "core_model_versions",
            "core_model_architecture_checks",
            "core_model_checkpoints",
            "core_model_events",
            "core_model_assignments",
        } <= tables
        assert {
            "ix_core_model_families_name",
            "ix_core_model_versions_status",
            "ix_core_model_configs_checksum",
            "ix_core_model_checkpoints_checksum",
            "ix_core_model_assignments_key",
        } <= indexes
        assert "core_model_events_immutable_delete" in triggers
        assert connection.execute("SELECT name FROM dataset_sources").fetchone()[0] == "Preserved"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_fresh_v8_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
