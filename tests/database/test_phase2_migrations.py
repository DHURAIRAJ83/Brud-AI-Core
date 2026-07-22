import sqlite3
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import (
    MigrationError,
    create_verified_backup,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
    verify_database,
)
from backend.database.schema import INITIAL_SCHEMA, SCHEMA_VERSION

REQUIRED_V2_TABLES = {
    "schema_migrations",
    "app_settings",
    "chat_sessions",
    "chat_messages",
    "dataset_sources",
    "dataset_records",
    "dataset_reviews",
    "dataset_versions",
    "dataset_version_items",
    "training_jobs",
    "training_job_events",
    "model_registry",
    "model_versions",
    "model_assignments",
    "user_feedback",
    "admin_approvals",
    "audit_logs",
}


def make_v1_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute(
        "CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, "
        "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    connection.executescript(INITIAL_SCHEMA)
    connection.execute("INSERT INTO schema_migrations(version) VALUES (1)")
    connection.commit()
    connection.close()


def test_upgrade_v1_to_v2_preserves_existing_data(tmp_path: Path) -> None:
    path = tmp_path / "brud.db"
    make_v1_database(path)
    with database_connection(path) as connection:
        connection.execute("INSERT INTO app_settings(key,value) VALUES (?,?)", ("legacy", "kept"))
        connection.commit()
    settings = Settings(
        database_path=path,
        database_backup_dir=tmp_path / "backups",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert backup is not None and backup.path.exists()
    assert integrity == "ok"
    with database_connection(path) as connection:
        assert (
            connection.execute(
                "SELECT value FROM app_settings WHERE key=?", ("legacy",)
            ).fetchone()[0]
            == "kept"
        )


def test_fresh_database_reaches_v2_with_all_tables(tmp_path: Path) -> None:
    path = tmp_path / "fresh.db"
    assert initialize_database(path) == 2
    with database_connection(path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert REQUIRED_V2_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_verified_backup_checksum_and_open(tmp_path: Path) -> None:
    path = tmp_path / "source.db"
    initialize_database(path)
    result = create_verified_backup(path, tmp_path / "backups")
    assert result.backup_checksum == sha256_file(result.path)
    assert verify_database(result.path).healthy


def test_upgrade_aborts_when_integrity_check_fails(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "source.db"
    make_v1_database(path)
    settings = Settings(
        database_path=path,
        database_backup_dir=tmp_path / "backups",
        allow_external_storage=True,
    )
    monkeypatch.setattr(
        "backend.database.migrations.verify_database",
        lambda _: (_ for _ in ()).throw(MigrationError("integrity failed")),
    )
    with pytest.raises(MigrationError, match="integrity failed"):
        upgrade_database(settings)
    assert current_schema_version(path) == 1
    assert not (tmp_path / "backups").exists()


def test_foreign_key_failure_is_reported(tmp_path: Path) -> None:
    path = tmp_path / "broken_fk.db"
    initialize_database(path)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys=OFF")
    connection.execute(
        "INSERT INTO dataset_reviews(public_id,dataset_record_id,decision,reviewer_type,"
        "previous_status,new_status) "
        "VALUES (?,?,?,?,?,?)",
        ("00000000-0000-0000-0000-000000000001", 999, "approve", "system", "draft", "approved"),
    )
    connection.commit()
    connection.close()
    with pytest.raises(MigrationError, match="foreign_key_violations"):
        verify_database(path)
