from pathlib import Path

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import (
    _apply_v1,
    _apply_v2,
    _apply_v3,
    _apply_v4,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)


def test_upgrade_v4_to_v5_is_additive_verified_and_backed_up(tmp_path: Path) -> None:
    database = tmp_path / "v4.db"
    with database_connection(database) as connection:
        _apply_v1(connection)
        _apply_v2(connection)
        _apply_v3(connection)
        _apply_v4(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved", "manual", "draft", "00000000-0000-0000-0000-000000000055"),
        )
        connection.commit()
    assert current_schema_version(database) == 4
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == 5 and backup is not None and integrity == "ok"
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
            "document_sources",
            "document_pages",
            "document_page_revisions",
            "document_processing_jobs",
            "document_processing_events",
            "document_candidates",
        } <= tables
        assert {
            "ix_documents_checksum",
            "ix_document_pages_status",
            "ix_document_candidates_hash",
        } <= indexes
        assert {
            "document_events_immutable_update",
            "document_revisions_immutable_delete",
        } <= triggers
        assert connection.execute("SELECT name FROM dataset_sources").fetchone()[0] == "Preserved"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_fresh_v5_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    initialize_database(database)
    assert current_schema_version(database) == 5
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
