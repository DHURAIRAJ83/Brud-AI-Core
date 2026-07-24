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
    _apply_v13,
    _apply_v14,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE15_TABLES = {
    "inference_runtime_profiles",
    "inference_runtime_instances",
    "inference_runtime_health_checks",
    "inference_model_compatibility_assessments",
    "inference_assignment_scopes",
    "inference_model_assignments",
    "inference_assignment_versions",
    "inference_assignment_approvals",
    "inference_assignment_events",
    "inference_sessions",
    "inference_requests",
    "inference_results",
    "inference_failures",
    "inference_canary_runs",
    "inference_canary_results",
    "inference_runtime_manifests",
}

APPLY_THROUGH_V14 = (
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
    _apply_v13,
    _apply_v14,
)


def test_fresh_database_reaches_schema_15(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE15_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_014_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 014 still behaves exactly as it did before Phase 15 existed."""
    database = tmp_path / "v14_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V14:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 14
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 14
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"model_releases", "model_release_families"} <= tables
        assert not (PHASE15_TABLES & tables)
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_14_upgrades_to_15(tmp_path: Path) -> None:
    database = tmp_path / "v14.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V14:
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved Phase14 Row", "manual", "draft", "00000000-0000-0000-0000-000000000099"),
        )
        connection.commit()
    assert current_schema_version(database) == 14
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
        assert PHASE15_TABLES <= tables
        assert {
            "ix_inference_runtime_instances_profile",
            "ix_inference_model_compatibility_release",
            "ix_model_assignments_scope",
            "ix_inference_requests_assignment",
        } <= indexes
        assert {
            "inference_runtime_health_checks_immutable_update",
            "inference_model_compatibility_immutable_update",
            "model_assignment_versions_immutable_update",
            "model_assignment_approvals_immutable_update",
            "model_assignment_events_immutable_update",
            "inference_requests_immutable_update",
            "inference_results_immutable_update",
            "inference_failures_immutable_update",
            "inference_canary_runs_immutable_update",
            "inference_canary_results_immutable_update",
            "inference_runtime_manifests_immutable_update",
        } <= triggers
        assert (
            connection.execute("SELECT name FROM dataset_sources").fetchone()[0]
            == "Preserved Phase14 Row"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_15_upgrade_is_a_no_op(tmp_path: Path) -> None:
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


def test_migration_15_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 15"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase15_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
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


def test_runtime_profiles_and_instances_are_mutable(tmp_path: Path) -> None:
    """profiles/instances are lifecycle rows, not append-only evidence."""
    database = tmp_path / "mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO inference_runtime_profiles(public_id,name,maximum_context_length,
            maximum_new_tokens,minimum_available_memory_bytes,minimum_available_disk_bytes,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000p1",
                "cpu-profile",
                512,
                128,
                1_000_000,
                1_000_000,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        profile_id = connection.execute(
            "SELECT id FROM inference_runtime_profiles WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000p1",),
        ).fetchone()[0]
        connection.execute(
            "UPDATE inference_runtime_profiles SET maximum_new_tokens=256 WHERE id=?",
            (profile_id,),
        )
        connection.execute(
            """INSERT INTO inference_runtime_instances(public_id,inference_runtime_profile_id,
            status) VALUES (?,?,?)""",
            ("00000000-0000-0000-0000-0000000000p2", profile_id, "offline"),
        )
        connection.commit()
        instance_id = connection.execute(
            "SELECT id FROM inference_runtime_instances WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000p2",),
        ).fetchone()[0]
        connection.execute(
            "UPDATE inference_runtime_instances SET status='ready' WHERE id=?",
            (instance_id,),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status, maximum_new_tokens FROM inference_runtime_instances "
            "JOIN inference_runtime_profiles ON inference_runtime_profiles.id = "
            "inference_runtime_instances.inference_runtime_profile_id "
            "WHERE inference_runtime_instances.id=?",
            (instance_id,),
        ).fetchone()
        assert row[0] == "ready"
        assert row[1] == 256


def test_append_only_phase15_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO inference_runtime_profiles(public_id,name,maximum_context_length,
            maximum_new_tokens,minimum_available_memory_bytes,minimum_available_disk_bytes,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000q1",
                "cpu-profile-2",
                512,
                128,
                1_000_000,
                1_000_000,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        profile_id = connection.execute(
            "SELECT id FROM inference_runtime_profiles WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000q1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO inference_runtime_instances(public_id,inference_runtime_profile_id,
            status) VALUES (?,?,?)""",
            ("00000000-0000-0000-0000-0000000000q2", profile_id, "offline"),
        )
        instance_id = connection.execute(
            "SELECT id FROM inference_runtime_instances WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000q2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO inference_runtime_health_checks(public_id,
            inference_runtime_instance_id,check_type,status) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000q3", instance_id,
                "runtime_process", "healthy",
            ),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """UPDATE inference_runtime_health_checks SET status='degraded'
                WHERE inference_runtime_instance_id=?""",
                (instance_id,),
            )
