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
    _apply_v8,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION


def test_upgrade_v8_to_v9_is_additive_verified_and_backed_up(tmp_path: Path) -> None:
    database = tmp_path / "v8.db"
    with database_connection(database) as connection:
        for apply in (
            _apply_v1,
            _apply_v2,
            _apply_v3,
            _apply_v4,
            _apply_v5,
            _apply_v6,
            _apply_v7,
            _apply_v8,
        ):
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved", "manual", "draft", "00000000-0000-0000-0000-000000000099"),
        )
        connection.commit()
    assert current_schema_version(database) == 8
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION == 11
    assert backup is not None and backup.path.is_file()
    assert sha256_file(backup.path) == backup.backup_checksum
    assert integrity == "ok"
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
            "pretraining_jobs",
            "pretraining_job_events",
            "pretraining_metrics",
            "pretraining_checkpoints",
            "pretraining_evaluations",
            "pretraining_evaluation_results",
            "training_worker_leases",
        } <= tables
        assert {
            "ix_pretraining_jobs_status",
            "ix_pretraining_jobs_refs",
            "ix_pretraining_metrics_job_step",
            "ix_pretraining_checkpoints_job",
            "ix_pretraining_checkpoints_checksum",
            "ix_training_worker_leases_job",
        } <= indexes
        assert "pretraining_events_immutable_delete" in triggers
        assert connection.execute("SELECT name FROM dataset_sources").fetchone()[0] == "Preserved"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_fresh_v9_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    initialize_database(database)
    assert current_schema_version(database) == 11
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 11
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
