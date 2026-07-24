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
    _apply_v12,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE13_TABLES = {
    "model_evaluation_suites",
    "model_evaluation_fixture_sets",
    "model_evaluation_fixtures",
    "model_evaluation_runs",
    "model_evaluation_outputs",
    "model_evaluation_metrics",
    "model_evaluation_issues",
    "model_evaluation_human_reviews",
    "model_evaluation_comparisons",
    "model_chat_readiness_assessments",
    "model_evaluation_manifests",
}

APPLY_THROUGH_V12 = (
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
    _apply_v12,
)


def test_fresh_database_reaches_schema_13(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE13_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_012_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 012 still behaves exactly as it did before Phase 13 existed."""
    database = tmp_path / "v12_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V12:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 12
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 12
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"instruction_tuning_experiments", "pretraining_jobs"} <= tables
        assert not (PHASE13_TABLES & tables)
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_12_upgrades_to_13(tmp_path: Path) -> None:
    database = tmp_path / "v12.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V12:
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved Phase12 Row", "manual", "draft", "00000000-0000-0000-0000-000000000099"),
        )
        connection.commit()
    assert current_schema_version(database) == 12
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
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
        assert PHASE13_TABLES <= tables
        assert {
            "ix_model_evaluation_suites_status",
            "ix_model_evaluation_fixture_sets_suite",
            "ix_model_evaluation_fixtures_set",
            "ix_model_evaluation_runs_suite",
        } <= indexes
        assert {
            "model_evaluation_fixture_sets_immutable_update",
            "model_evaluation_fixtures_immutable_update",
            "model_evaluation_outputs_immutable_update",
            "model_evaluation_metrics_immutable_update",
            "model_evaluation_issues_immutable_update",
            "model_evaluation_human_reviews_immutable_update",
            "model_evaluation_comparisons_immutable_update",
            "model_chat_readiness_assessments_immutable_update",
            "model_evaluation_manifests_immutable_update",
        } <= triggers
        assert (
            connection.execute("SELECT name FROM dataset_sources").fetchone()[0]
            == "Preserved Phase12 Row"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_13_upgrade_is_a_no_op(tmp_path: Path) -> None:
    database = tmp_path / "already_current.db"
    initialize_database(database)
    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert backup is None
    assert integrity == "ok"
    assert not (tmp_path / "backups").exists() or not list((tmp_path / "backups").iterdir())


def test_migration_13_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 13"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase13_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
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


def test_model_evaluation_suites_and_runs_are_mutable(tmp_path: Path) -> None:
    """suites/runs are lifecycle rows, not append-only evidence."""
    database = tmp_path / "mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO model_evaluation_suites(public_id,name,version,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000g1",
                "suite", "1", "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE model_evaluation_suites SET status='validated' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000g1",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM model_evaluation_suites WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000g1",),
        ).fetchone()
        assert row[0] == "validated"


def test_append_only_phase13_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO model_evaluation_suites(public_id,name,version,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000g2",
                "suite2", "1", "00000000-0000-0000-0000-000000000001",
            ),
        )
        suite_id = connection.execute(
            "SELECT id FROM model_evaluation_suites WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000g2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO model_evaluation_fixture_sets(public_id,model_evaluation_suite_id,
            name,created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000g3", suite_id, "set1",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """UPDATE model_evaluation_fixture_sets SET fixture_count=99
                WHERE model_evaluation_suite_id=?""",
                (suite_id,),
            )
