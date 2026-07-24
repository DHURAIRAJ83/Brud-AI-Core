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
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE14_TABLES = {
    "model_release_families",
    "model_release_candidates",
    "model_release_artifacts",
    "model_release_manifests",
    "model_release_model_cards",
    "model_release_eligibility_assessments",
    "model_release_issues",
    "model_release_approvals",
    "model_releases",
    "model_release_comparisons",
    "model_release_rollback_plans",
    "model_release_rollback_events",
    "model_release_bundles",
}

APPLY_THROUGH_V13 = (
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
)


def test_fresh_database_reaches_schema_14(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE14_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_013_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 013 still behaves exactly as it did before Phase 14 existed."""
    database = tmp_path / "v13_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V13:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 13
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 13
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"model_evaluation_suites", "instruction_tuning_candidates"} <= tables
        assert not (PHASE14_TABLES & tables)
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_13_upgrades_to_14(tmp_path: Path) -> None:
    database = tmp_path / "v13.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V13:
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved Phase13 Row", "manual", "draft", "00000000-0000-0000-0000-000000000098"),
        )
        connection.commit()
    assert current_schema_version(database) == 13
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
        assert PHASE14_TABLES <= tables
        assert {
            "ix_model_release_families_status",
            "ix_model_release_candidates_family",
            "ix_model_release_artifacts_candidate",
            "ix_model_releases_family",
        } <= indexes
        assert {
            "model_release_artifacts_immutable_update",
            "model_release_manifests_immutable_update",
            "model_release_model_cards_immutable_update",
            "model_release_eligibility_immutable_update",
            "model_release_issues_immutable_update",
            "model_release_approvals_immutable_update",
            "model_release_comparisons_immutable_update",
            "model_release_rollback_events_immutable_update",
            "model_release_bundles_immutable_update",
        } <= triggers
        assert (
            connection.execute("SELECT name FROM dataset_sources").fetchone()[0]
            == "Preserved Phase13 Row"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_14_upgrade_is_a_no_op(tmp_path: Path) -> None:
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


def test_migration_14_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 14"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase14_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
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


def test_model_release_families_and_candidates_are_mutable(tmp_path: Path) -> None:
    """families/candidates are lifecycle rows, not append-only evidence."""
    database = tmp_path / "mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO model_release_families(public_id,name,slug,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000h1",
                "family", "family-slug", "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE model_release_families SET lifecycle_status='active' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000h1",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT lifecycle_status FROM model_release_families WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000h1",),
        ).fetchone()
        assert row[0] == "active"


def test_append_only_phase14_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO model_release_families(public_id,name,slug,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000h2",
                "family2", "family2-slug", "00000000-0000-0000-0000-000000000001",
            ),
        )
        family_id = connection.execute(
            "SELECT id FROM model_release_families WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000h2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO model_release_candidates(public_id,model_release_family_id,
            core_model_version_id,checkpoint_id,tokenizer_version_id,
            created_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000h3", family_id, 1, 1, 1,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        candidate_id = connection.execute(
            "SELECT id FROM model_release_candidates WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000h3",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO model_release_artifacts(public_id,model_release_candidate_id,
            artifact_type,logical_name,storage_key,checksum,checksum_algorithm)
            VALUES (?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000h4", candidate_id, "model_checkpoint",
                "checkpoint", "checkpoints/example", "a" * 64, "sha256",
            ),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """UPDATE model_release_artifacts SET verification_status='verified'
                WHERE model_release_candidate_id=?""",
                (candidate_id,),
            )
