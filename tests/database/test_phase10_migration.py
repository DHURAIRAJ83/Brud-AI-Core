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
    _apply_v9,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE10_TABLES = {
    "worker_heartbeats",
    "training_recovery_attempts",
    "training_dataset_coverage",
    "training_stream_manifests",
    "training_run_summaries",
    "training_quality_assessments",
    "training_quality_issues",
    "training_checkpoint_comparisons",
    "training_run_comparisons",
    "checkpoint_retention_actions",
}


def test_fresh_database_reaches_schema_10(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE10_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase_9_migration_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 009 still behaves exactly as it did before Phase 10 existed."""
    database = tmp_path / "v9_only.db"
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
            _apply_v9,
        ):
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 9
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 9
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"pretraining_jobs", "training_worker_leases"} <= tables
        assert not (PHASE10_TABLES & tables)
        columns = {row[1] for row in connection.execute('PRAGMA table_info("pretraining_jobs")')}
        assert "lease_generation" not in columns
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_9_upgrades_to_10(tmp_path: Path) -> None:
    database = tmp_path / "v9.db"
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
            _apply_v9,
        ):
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved Phase9 Row", "manual", "draft", "00000000-0000-0000-0000-000000000098"),
        )
        connection.commit()
    assert current_schema_version(database) == 9
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
        assert PHASE10_TABLES <= tables
        assert {
            "ix_worker_heartbeats_status",
            "ix_training_recovery_attempts_job",
            "ix_training_dataset_coverage_job",
            "ix_training_stream_manifests_job",
            "ix_checkpoint_retention_actions_job",
        } <= indexes
        assert {
            "training_recovery_attempts_immutable_update",
            "training_dataset_coverage_immutable_update",
            "training_quality_issues_immutable_update",
        } <= triggers
        columns = {row[1] for row in connection.execute('PRAGMA table_info("pretraining_jobs")')}
        assert {
            "lease_generation",
            "recovery_required",
            "latest_stream_checksum_sha256",
            "latest_coverage_public_id",
            "quality_readiness_status",
            "best_checkpoint_public_id",
        } <= columns
        lease_columns = {
            row[1] for row in connection.execute('PRAGMA table_info("training_worker_leases")')
        }
        expected_lease_columns = {
            "lease_generation", "owner_public_id", "released_at", "release_reason",
        }
        assert expected_lease_columns <= lease_columns
        assert (
            connection.execute("SELECT name FROM dataset_sources").fetchone()[0]
            == "Preserved Phase9 Row"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_10_upgrade_is_a_no_op(tmp_path: Path) -> None:
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


def test_migration_10_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 10"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase10_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
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


def test_worker_heartbeats_immutability_does_not_apply(tmp_path: Path) -> None:
    """worker_heartbeats must remain mutable so heartbeats can be renewed."""
    database = tmp_path / "heartbeats.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO worker_heartbeats(public_id,worker_id,status)
            VALUES (?,?,?)""",
            ("00000000-0000-0000-0000-0000000000a1", "worker-a", "idle"),
        )
        connection.commit()
        connection.execute(
            "UPDATE worker_heartbeats SET status='running' WHERE worker_id='worker-a'"
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM worker_heartbeats WHERE worker_id='worker-a'"
        ).fetchone()
        assert row[0] == "running"


def test_append_only_phase10_tables_reject_updates(tmp_path: Path) -> None:
    import sqlite3

    import pytest

    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        # Foreign key enforcement is disabled only for this isolated trigger check;
        # the goal is proving append-only immutability, not the job reference graph.
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO pretraining_jobs(public_id,name,status,dataset_version_id,
            tokenizer_version_id,core_model_version_id,job_mode,configuration_json,
            config_checksum_sha256,initialization_seed,sampling_seed,total_steps,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000b1",
                "irrelevant",
                "draft",
                1,
                1,
                1,
                "smoke_pretraining",
                "{}",
                "a" * 64,
                1,
                1,
                1,
                "00000000-0000-0000-0000-0000000000b2",
            ),
        )
        job_id = connection.execute(
            "SELECT id FROM pretraining_jobs WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000b1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO training_dataset_coverage(public_id,pretraining_job_id,split,
            stream_checksum_sha256) VALUES (?,?,?,?)""",
            ("00000000-0000-0000-0000-0000000000c1", job_id, "train", "a" * 64),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE training_dataset_coverage SET total_records=99 WHERE pretraining_job_id=?",
                (job_id,),
            )
