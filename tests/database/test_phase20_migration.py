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
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE20_TABLES = {
    "corpus_ingestion_jobs",
    "corpus_ingestion_events",
    "corpus_normalization_profiles",
    "corpus_segmentation_profiles",
    "corpus_protected_content_sets",
    "corpus_protected_content_entries",
    "corpus_partition_previews",
    "corpus_tokenizer_analyses",
    "corpus_tokenizer_analysis_metrics",
    "corpus_readiness_evaluations",
    "corpus_readiness_dimensions",
    "corpus_releases",
    "corpus_release_approvals",
}

APPLY_THROUGH_V19 = (
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
)


def test_fresh_database_reaches_schema_20(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE20_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_019_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 019 still behaves exactly as it did before Phase 20 existed."""
    database = tmp_path / "v19_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V19:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 19
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 19
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"corpus_policies", "corpus_source_registries"} <= tables
        assert not (PHASE20_TABLES & tables)
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(corpus_source_registries)")
        }
        assert "production_lifecycle_status" not in columns
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_19_upgrades_to_20(tmp_path: Path) -> None:
    database = tmp_path / "v19.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V19:
            apply(connection)
        connection.execute(
            """INSERT INTO corpus_policies(public_id,name,created_by_admin_public_id)
            VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-000000000p20",
                "Preserved Phase19 Policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
    assert current_schema_version(database) == 19
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
        assert PHASE20_TABLES <= tables
        assert {
            "ix_corpus_ingestion_jobs_source",
            "ix_corpus_tokenizer_analyses_tokenizer",
            "ix_corpus_readiness_dimensions_evaluation",
        } <= indexes
        assert {
            "corpus_ingestion_events_immutable_update",
            "corpus_protected_content_entries_immutable_update",
            "corpus_partition_previews_immutable_update",
            "corpus_tokenizer_analysis_metrics_immutable_update",
            "corpus_readiness_dimensions_immutable_update",
            "corpus_release_approvals_immutable_update",
        } <= triggers
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(corpus_source_registries)")
        }
        assert {
            "production_lifecycle_status",
            "original_url",
            "acquisition_date",
            "reviewed_by_admin_public_id",
            "reviewed_at",
        } <= columns
        label_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(corpus_language_assessments)")
        }
        assert {"method", "review_status"} <= label_columns
        assert (
            connection.execute(
                "SELECT name FROM corpus_policies WHERE public_id=?",
                ("00000000-0000-0000-0000-000000000p20",),
            ).fetchone()[0]
            == "Preserved Phase19 Policy"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_20_upgrade_is_a_no_op(tmp_path: Path) -> None:
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


def test_migration_20_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 20"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase20_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
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


def test_corpus_ingestion_jobs_are_mutable(tmp_path: Path) -> None:
    """corpus_ingestion_jobs needs a create(queued)->run->complete
    two-phase flow, mirroring Phase 19's own extraction/normalization/
    dedup/contamination/export runs."""

    database = tmp_path / "ingestion_mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO corpus_policies(public_id,name,created_by_admin_public_id)
            VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000j1",
                "policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        policy_id = connection.execute(
            "SELECT id FROM corpus_policies WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000j1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_source_registries(public_id,corpus_policy_id,title,
            source_type,created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000j2",
                policy_id,
                "Source",
                "uploaded_pdf",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        source_id = connection.execute(
            "SELECT id FROM corpus_source_registries WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000j2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_ingestion_jobs(public_id,source_id,format,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000j3",
                source_id,
                "pdf",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE corpus_ingestion_jobs SET status='completed' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000j3",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM corpus_ingestion_jobs WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000j3",),
        ).fetchone()
        assert row[0] == "completed"


def test_append_only_phase20_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO corpus_protected_content_sets(public_id,name,set_type,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000a1",
                "Set",
                "validation_dataset",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        set_id = connection.execute(
            "SELECT id FROM corpus_protected_content_sets WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000a1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_protected_content_entries(public_id,
            protected_content_set_id,raw_checksum_sha256,normalized_checksum_sha256)
            VALUES (?,?,?,?)""",
            ("00000000-0000-0000-0000-0000000000a2", set_id, "a" * 64, "b" * 64),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE corpus_protected_content_entries SET raw_checksum_sha256=? "
                "WHERE public_id=?",
                ("c" * 64, "00000000-0000-0000-0000-0000000000a2"),
            )
        connection.rollback()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM corpus_protected_content_entries WHERE public_id=?",
                ("00000000-0000-0000-0000-0000000000a2",),
            )
