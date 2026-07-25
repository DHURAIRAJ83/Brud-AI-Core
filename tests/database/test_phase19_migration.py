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
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE19_TABLES = {
    "corpus_policies",
    "corpus_source_registries",
    "corpus_source_licences",
    "corpus_source_snapshots",
    "corpus_source_files",
    "corpus_extraction_runs",
    "corpus_extracted_documents",
    "corpus_normalization_runs",
    "corpus_normalized_documents",
    "corpus_segments",
    "corpus_segment_locations",
    "corpus_language_assessments",
    "corpus_domain_assessments",
    "corpus_style_assessments",
    "corpus_quality_assessments",
    "corpus_quality_issues",
    "corpus_privacy_findings",
    "corpus_safety_findings",
    "corpus_deduplication_runs",
    "corpus_duplicate_clusters",
    "corpus_duplicate_members",
    "corpus_contamination_runs",
    "corpus_contamination_findings",
    "corpus_collections",
    "corpus_collection_members",
    "corpus_balance_policies",
    "corpus_builds",
    "corpus_build_members",
    "corpus_partitions",
    "corpus_versions",
    "corpus_exports",
    "corpus_export_shards",
    "corpus_manifests",
    "corpus_comparisons",
}

APPLY_THROUGH_V18 = (
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
)


def test_fresh_database_reaches_schema_19(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE19_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_018_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 018 still behaves exactly as it did before Phase 19 existed."""
    database = tmp_path / "v18_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V18:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 18
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 18
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"feedback_policies", "feedback_dataset_candidates"} <= tables
        assert not (PHASE19_TABLES & tables)
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_18_upgrades_to_19(tmp_path: Path) -> None:
    database = tmp_path / "v18.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V18:
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved Phase18 Row", "manual", "draft", "00000000-0000-0000-0000-000000000097"),
        )
        connection.commit()
    assert current_schema_version(database) == 18
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
        assert PHASE19_TABLES <= tables
        assert {
            "ix_corpus_source_registries_status",
            "ix_corpus_build_members_build",
            "ix_corpus_export_shards_export",
        } <= indexes
        assert {
            "corpus_extracted_documents_immutable_update",
            "corpus_normalized_documents_immutable_update",
            "corpus_segments_immutable_update",
            "corpus_segment_locations_immutable_update",
            "corpus_language_assessments_immutable_update",
            "corpus_domain_assessments_immutable_update",
            "corpus_style_assessments_immutable_update",
            "corpus_quality_assessments_immutable_update",
            "corpus_quality_issues_immutable_update",
            "corpus_privacy_findings_immutable_update",
            "corpus_safety_findings_immutable_update",
            "corpus_duplicate_clusters_immutable_update",
            "corpus_duplicate_members_immutable_update",
            "corpus_contamination_findings_immutable_update",
            "corpus_collection_members_immutable_update",
            "corpus_build_members_immutable_update",
            "corpus_partitions_immutable_update",
            "corpus_export_shards_immutable_update",
            "corpus_manifests_immutable_update",
            "corpus_comparisons_immutable_update",
        } <= triggers
        assert (
            connection.execute("SELECT name FROM dataset_sources").fetchone()[0]
            == "Preserved Phase18 Row"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_19_upgrade_is_a_no_op(tmp_path: Path) -> None:
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


def test_migration_19_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 19"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase19_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
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


def test_corpus_lifecycle_tables_are_mutable(tmp_path: Path) -> None:
    """policies/sources/licences/snapshots/files/extraction runs/
    normalization runs/dedup runs/contamination runs/collections/
    balance policies/builds/versions/exports are lifecycle rows."""

    database = tmp_path / "mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO corpus_policies(public_id,name,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000m1", "policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE corpus_policies SET lifecycle_status='active' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000m1",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT lifecycle_status FROM corpus_policies WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000m1",),
        ).fetchone()
        assert row[0] == "active"


def test_corpus_extraction_runs_are_mutable(tmp_path: Path) -> None:
    """corpus_extraction_runs needs a create(draft)->execute(completed)
    two-phase flow, exactly like every prior phase's evaluation/regression
    runs -- and unlike those phases, this phase's own spec already
    correctly pre-classifies it as mutable."""

    database = tmp_path / "extraction_mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO corpus_policies(public_id,name,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000e1", "policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        policy_id = connection.execute(
            "SELECT id FROM corpus_policies WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000e1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_source_registries(public_id,corpus_policy_id,title,
            source_type,created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000e2", policy_id, "Source", "manual_admin_text",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        source_id = connection.execute(
            "SELECT id FROM corpus_source_registries WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000e2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_source_snapshots(public_id,source_id,version_number,
            source_checksum_sha256,file_inventory_checksum_sha256,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000e3", source_id, 1, "a" * 64, "b" * 64,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        snapshot_id = connection.execute(
            "SELECT id FROM corpus_source_snapshots WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000e3",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_extraction_runs(public_id,snapshot_id,extraction_method,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000e4", snapshot_id, "plain_text",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE corpus_extraction_runs SET status='completed' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000e4",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM corpus_extraction_runs WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000e4",),
        ).fetchone()
        assert row[0] == "completed"


def test_append_only_phase19_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO corpus_policies(public_id,name,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000b1", "policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        policy_id = connection.execute(
            "SELECT id FROM corpus_policies WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000b1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_source_registries(public_id,corpus_policy_id,title,
            source_type,created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000b2", policy_id, "Source", "manual_admin_text",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        source_id = connection.execute(
            "SELECT id FROM corpus_source_registries WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000b2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_source_snapshots(public_id,source_id,version_number,
            source_checksum_sha256,file_inventory_checksum_sha256,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000b3", source_id, 1, "a" * 64, "b" * 64,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        snapshot_id = connection.execute(
            "SELECT id FROM corpus_source_snapshots WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000b3",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_extraction_runs(public_id,snapshot_id,extraction_method,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000b4", snapshot_id, "plain_text",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        extraction_run_id = connection.execute(
            "SELECT id FROM corpus_extraction_runs WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000b4",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_source_files(public_id,snapshot_id,logical_filename,
            safe_relative_storage_key,mime_type,size_bytes,checksum_sha256)
            VALUES (?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000b5", snapshot_id, "a.txt", "a.txt",
                "text/plain", 10, "c" * 64,
            ),
        )
        source_file_id = connection.execute(
            "SELECT id FROM corpus_source_files WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000b5",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO corpus_extracted_documents(public_id,extraction_run_id,
            source_file_id,document_sequence,raw_text,raw_text_checksum_sha256,character_count)
            VALUES (?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000b6", extraction_run_id, source_file_id, 1,
                "hello", "d" * 64, 5,
            ),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE corpus_extracted_documents SET character_count=99 WHERE public_id=?",
                ("00000000-0000-0000-0000-0000000000b6",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM corpus_extracted_documents WHERE public_id=?",
                ("00000000-0000-0000-0000-0000000000b6",),
            )
