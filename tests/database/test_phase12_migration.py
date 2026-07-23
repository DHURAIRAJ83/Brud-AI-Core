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
    _apply_v11,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE12_TABLES = {
    "instruction_tuning_experiments",
    "instruction_tuning_runs",
    "instruction_dataset_profiles",
    "instruction_format_templates",
    "instruction_tuning_metrics",
    "instruction_tuning_evaluations",
    "instruction_tuning_evaluation_results",
    "instruction_learning_checks",
    "instruction_tuning_candidates",
    "instruction_reproducibility_manifests",
}

APPLY_THROUGH_V11 = (
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
    _apply_v11,
)


def test_fresh_database_reaches_schema_12(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION == 12
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE12_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 12
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_011_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 011 still behaves exactly as it did before Phase 12 existed."""
    database = tmp_path / "v11_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V11:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 11
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 11
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"base_training_experiments", "pretraining_jobs"} <= tables
        assert not (PHASE12_TABLES & tables)
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_11_upgrades_to_12(tmp_path: Path) -> None:
    database = tmp_path / "v11.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V11:
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved Phase11 Row", "manual", "draft", "00000000-0000-0000-0000-000000000098"),
        )
        connection.commit()
    assert current_schema_version(database) == 11
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION == 12
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
        assert PHASE12_TABLES <= tables
        assert {
            "ix_instruction_tuning_experiments_status",
            "ix_instruction_tuning_runs_experiment",
            "ix_instruction_dataset_profiles_experiment",
            "ix_instruction_tuning_metrics_run",
        } <= indexes
        assert {
            "instruction_format_templates_immutable_update",
            "instruction_dataset_profiles_immutable_update",
            "instruction_tuning_metrics_immutable_update",
            "instruction_tuning_evaluations_immutable_update",
            "instruction_tuning_evaluation_results_immutable_update",
            "instruction_learning_checks_immutable_update",
            "instruction_tuning_candidates_immutable_update",
            "instruction_reproducibility_manifests_immutable_update",
        } <= triggers
        assert (
            connection.execute("SELECT name FROM dataset_sources").fetchone()[0]
            == "Preserved Phase11 Row"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_12_upgrade_is_a_no_op(tmp_path: Path) -> None:
    database = tmp_path / "already_12.db"
    initialize_database(database)
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == 12
    assert backup is None
    assert integrity == "ok"
    assert not (tmp_path / "backups").exists() or not list((tmp_path / "backups").iterdir())


def test_migration_12_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 12"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase12_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
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


def test_instruction_tuning_experiments_and_runs_are_mutable(tmp_path: Path) -> None:
    """experiments/runs are lifecycle rows, not append-only evidence."""
    database = tmp_path / "mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO instruction_tuning_experiments(public_id,name,
            base_core_model_version_id,source_base_checkpoint_id,dataset_version_id,
            tokenizer_version_id,created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000f1",
                "exp",
                1,
                1,
                1,
                1,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE instruction_tuning_experiments SET status='profiled' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000f1",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM instruction_tuning_experiments WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000f1",),
        ).fetchone()
        assert row[0] == "profiled"


def test_append_only_phase12_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO instruction_tuning_experiments(public_id,name,
            base_core_model_version_id,source_base_checkpoint_id,dataset_version_id,
            tokenizer_version_id,created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000f2",
                "exp",
                1,
                1,
                1,
                1,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        experiment_id = connection.execute(
            "SELECT id FROM instruction_tuning_experiments WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000f2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO instruction_dataset_profiles(public_id,
            instruction_tuning_experiment_id,dataset_version_id,input_stream_checksum_sha256,
            label_stream_checksum_sha256,profile_checksum_sha256) VALUES (?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000f3",
                experiment_id,
                1,
                "a" * 64,
                "b" * 64,
                "c" * 64,
            ),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """UPDATE instruction_dataset_profiles SET total_records=99
                WHERE instruction_tuning_experiment_id=?""",
                (experiment_id,),
            )
