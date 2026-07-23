import sqlite3
from pathlib import Path

import pytest

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
    _apply_v9,
    _apply_v10,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE11_TABLES = {
    "base_training_experiments",
    "base_training_experiment_runs",
    "base_training_dataset_profiles",
    "base_training_language_metrics",
    "base_training_learning_checks",
    "base_training_candidate_selections",
    "base_training_reproducibility_manifests",
}

APPLY_THROUGH_V10 = (
    _apply_v1,
    _apply_v2,
    _apply_v3,
    _apply_v4,
    _apply_v5,
    _apply_v6,
    _apply_v7,
    _apply_v8,
    _apply_v9,
    _apply_v10,
)


def test_fresh_database_reaches_schema_11(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION == 11
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE11_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 11
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_010_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 010 still behaves exactly as it did before Phase 11 existed."""
    database = tmp_path / "v10_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V10:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 10
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 10
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"worker_heartbeats", "pretraining_jobs"} <= tables
        assert not (PHASE11_TABLES & tables)
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_10_upgrades_to_11(tmp_path: Path) -> None:
    database = tmp_path / "v10.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V10:
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved Phase10 Row", "manual", "draft", "00000000-0000-0000-0000-000000000097"),
        )
        connection.commit()
    assert current_schema_version(database) == 10
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
        assert PHASE11_TABLES <= tables
        assert {
            "ix_base_training_experiments_status",
            "ix_base_training_experiment_runs_experiment",
            "ix_base_training_dataset_profiles_experiment",
            "ix_base_training_language_metrics_run",
        } <= indexes
        assert {
            "base_training_dataset_profiles_immutable_update",
            "base_training_language_metrics_immutable_update",
            "base_training_learning_checks_immutable_update",
            "base_training_candidate_selections_immutable_update",
            "base_training_reproducibility_manifests_immutable_update",
        } <= triggers
        assert (
            connection.execute("SELECT name FROM dataset_sources").fetchone()[0]
            == "Preserved Phase10 Row"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_11_upgrade_is_a_no_op(tmp_path: Path) -> None:
    database = tmp_path / "already_11.db"
    initialize_database(database)
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == 11
    assert backup is None
    assert integrity == "ok"
    assert not (tmp_path / "backups").exists() or not list((tmp_path / "backups").iterdir())


def test_migration_11_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 11"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase11_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.db"
    second = tmp_path / "second.db"
    initialize_database(first)
    initialize_database(second)
    with database_connection(first) as a, database_connection(second) as b:
        objects_a = {
            (row[0], row[1])
            for row in a.execute(
                "SELECT type, name FROM sqlite_master WHERE type IN ('table','index','trigger')"
            )
        }
        objects_b = {
            (row[0], row[1])
            for row in b.execute(
                "SELECT type, name FROM sqlite_master WHERE type IN ('table','index','trigger')"
            )
        }
        assert objects_a == objects_b


def test_base_training_experiments_and_runs_are_mutable(tmp_path: Path) -> None:
    """experiments/runs are lifecycle rows, not append-only evidence."""
    database = tmp_path / "mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO base_training_experiments(public_id,name,dataset_version_id,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000d1",
                "exp",
                1,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE base_training_experiments SET status='profiled' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000d1",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM base_training_experiments WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000d1",),
        ).fetchone()
        assert row[0] == "profiled"


def test_append_only_phase11_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO base_training_experiments(public_id,name,dataset_version_id,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000e1",
                "exp",
                1,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        experiment_id = connection.execute(
            "SELECT id FROM base_training_experiments WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000e1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO base_training_dataset_profiles(public_id,base_training_experiment_id,
            dataset_version_id,profile_checksum_sha256) VALUES (?,?,?,?)""",
            ("00000000-0000-0000-0000-0000000000e2", experiment_id, 1, "a" * 64),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """UPDATE base_training_dataset_profiles SET total_records=99
                WHERE base_training_experiment_id=?""",
                (experiment_id,),
            )
