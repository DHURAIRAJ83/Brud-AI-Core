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
    _apply_v15,
    _apply_v16,
    _apply_v17,
    _apply_v18,
    _apply_v19,
    _apply_v20,
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE21A_TABLES = {
    "tokenizer_corpus_builds",
    "tokenizer_candidate_comparisons",
    "tokenizer_selection_evaluations",
    "pretraining_dataset_snapshots",
    "base_model_resource_estimates",
    "pretraining_smoke_runs",
    "base_model_readiness_evaluations",
    "base_model_readiness_dimensions",
}

APPLY_THROUGH_V20 = (
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
    _apply_v15,
    _apply_v16,
    _apply_v17,
    _apply_v18,
    _apply_v19,
    _apply_v20,
)


def test_fresh_database_reaches_schema_21(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE21A_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_020_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 020 still behaves exactly as it did before Phase 21A existed."""
    database = tmp_path / "v20_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V20:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 20
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 20
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"corpus_releases", "corpus_readiness_evaluations"} <= tables
        assert not (PHASE21A_TABLES & tables)
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_20_upgrades_to_21(tmp_path: Path) -> None:
    database = tmp_path / "v20.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V20:
            apply(connection)
        connection.execute(
            """INSERT INTO corpus_policies(public_id,name,created_by_admin_public_id)
            VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-000000000p21",
                "Preserved Phase20 Policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
    assert current_schema_version(database) == 20
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
        assert PHASE21A_TABLES <= tables
        assert {
            "ix_tokenizer_corpus_builds_release",
            "ix_pretraining_dataset_snapshots_release",
            "ix_base_model_readiness_dimensions_evaluation",
        } <= indexes
        assert {
            "tokenizer_selection_evaluations_immutable_update",
            "pretraining_dataset_snapshots_immutable_update",
            "base_model_readiness_dimensions_immutable_update",
        } <= triggers
        assert (
            connection.execute(
                "SELECT name FROM corpus_policies WHERE public_id=?",
                ("00000000-0000-0000-0000-000000000p21",),
            ).fetchone()[0]
            == "Preserved Phase20 Policy"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_21_upgrade_is_a_no_op(tmp_path: Path) -> None:
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


def test_migration_21_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 21"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase21a_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
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


def test_pretraining_smoke_runs_are_mutable(tmp_path: Path) -> None:
    """pretraining_smoke_runs needs a draft->running->completed flow."""

    database = tmp_path / "smoke_mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO pretraining_dataset_snapshots(public_id,corpus_release_id,
            dataset_version_id,tokenizer_version_id,manifest_checksum_sha256,
            tokenizer_checksum_sha256,maximum_sequence_length,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000s1",
                1,
                1,
                1,
                "a" * 64,
                "b" * 64,
                64,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        snapshot_id = connection.execute(
            "SELECT id FROM pretraining_dataset_snapshots WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000s1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO base_model_resource_estimates(public_id,profile_name,
            vocabulary_size,context_length,hidden_size,num_hidden_layers,
            num_attention_heads,intermediate_size,parameter_count,parameter_memory_bytes,
            gradient_memory_bytes,optimizer_state_memory_bytes,activation_memory_bytes,
            estimated_peak_ram_bytes,checkpoint_disk_bytes,optimizer_disk_bytes,
            estimated_tokens_per_second,estimated_training_duration_seconds_min,
            estimated_training_duration_seconds_max,safe_ram_ceiling_bytes,
            within_safe_limit,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000s2",
                "micro_smoke_test",
                1000,
                256,
                128,
                4,
                4,
                384,
                1_000_000,
                4_000_000,
                4_000_000,
                8_000_000,
                1_000_000,
                20_000_000,
                4_000_000,
                8_000_000,
                100.0,
                1,
                10,
                4_500_000_000,
                1,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        estimate_id = connection.execute(
            "SELECT id FROM base_model_resource_estimates WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000s2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO pretraining_smoke_runs(public_id,pretraining_dataset_snapshot_id,
            base_model_resource_estimate_id,created_by_admin_public_id)
            VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000s3",
                snapshot_id,
                estimate_id,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE pretraining_smoke_runs SET status='completed' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000s3",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM pretraining_smoke_runs WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000s3",),
        ).fetchone()
        assert row[0] == "completed"


def test_append_only_phase21a_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO pretraining_dataset_snapshots(public_id,corpus_release_id,
            dataset_version_id,tokenizer_version_id,manifest_checksum_sha256,
            tokenizer_checksum_sha256,maximum_sequence_length,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000a1",
                1,
                1,
                1,
                "a" * 64,
                "b" * 64,
                64,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE pretraining_dataset_snapshots SET maximum_sequence_length=128 "
                "WHERE public_id=?",
                ("00000000-0000-0000-0000-0000000000a1",),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM pretraining_dataset_snapshots WHERE public_id=?",
                ("00000000-0000-0000-0000-0000000000a1",),
            )
