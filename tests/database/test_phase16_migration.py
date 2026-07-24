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
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE16_TABLES = {
    "rag_knowledge_spaces",
    "rag_knowledge_sources",
    "rag_source_versions",
    "rag_chunk_sets",
    "rag_chunks",
    "rag_embedding_models",
    "rag_embedding_runs",
    "rag_chunk_embeddings",
    "rag_vector_indexes",
    "rag_keyword_indexes",
    "rag_retrieval_profiles",
    "rag_retrieval_runs",
    "rag_retrieved_chunks",
    "rag_context_assemblies",
    "rag_grounded_requests",
    "rag_grounded_answers",
    "rag_answer_citations",
    "rag_grounding_issues",
    "rag_evaluation_suites",
    "rag_evaluation_fixtures",
    "rag_evaluation_runs",
    "rag_evaluation_metrics",
    "rag_index_comparisons",
    "rag_manifests",
}

APPLY_THROUGH_V15 = (
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
)


def test_fresh_database_reaches_schema_16(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE16_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_015_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 015 still behaves exactly as it did before Phase 16 existed."""
    database = tmp_path / "v15_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V15:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 15
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 15
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"inference_runtime_profiles", "inference_model_assignments"} <= tables
        assert not (PHASE16_TABLES & tables)
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_15_upgrades_to_16(tmp_path: Path) -> None:
    database = tmp_path / "v15.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V15:
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved Phase15 Row", "manual", "draft", "00000000-0000-0000-0000-000000000097"),
        )
        connection.commit()
    assert current_schema_version(database) == 15
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
        assert PHASE16_TABLES <= tables
        assert {
            "ix_rag_knowledge_sources_space",
            "ix_rag_chunks_chunk_set",
            "ix_rag_vector_indexes_space",
            "ix_rag_retrieved_chunks_run",
        } <= indexes
        assert {
            "rag_chunks_immutable_update",
            "rag_chunk_embeddings_immutable_update",
            "rag_retrieval_runs_immutable_update",
            "rag_retrieved_chunks_immutable_update",
            "rag_context_assemblies_immutable_update",
            "rag_grounded_answers_immutable_update",
            "rag_answer_citations_immutable_update",
            "rag_grounding_issues_immutable_update",
            "rag_evaluation_fixtures_immutable_update",
            "rag_evaluation_metrics_immutable_update",
            "rag_index_comparisons_immutable_update",
            "rag_manifests_immutable_update",
        } <= triggers
        assert (
            connection.execute("SELECT name FROM dataset_sources").fetchone()[0]
            == "Preserved Phase15 Row"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_16_upgrade_is_a_no_op(tmp_path: Path) -> None:
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


def test_migration_16_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 16"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase16_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
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


def test_knowledge_spaces_and_sources_are_mutable(tmp_path: Path) -> None:
    """spaces/sources/versions/chunk-sets/indexes/profiles are lifecycle rows."""
    database = tmp_path / "mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO rag_knowledge_spaces(public_id,name,slug,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000s1",
                "space", "space-slug", "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE rag_knowledge_spaces SET lifecycle_status='active' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000s1",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT lifecycle_status FROM rag_knowledge_spaces WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000s1",),
        ).fetchone()
        assert row[0] == "active"


def test_grounded_requests_are_mutable(tmp_path: Path) -> None:
    """rag_grounded_requests is a two-phase create-then-resolve lifecycle
    row (accepted -> completed/insufficient_evidence/...), not append-only
    -- mirrors the rag_embedding_runs/rag_evaluation_runs precedent."""

    database = tmp_path / "grounded_requests_mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO rag_grounded_requests(public_id,retrieval_run_id,
            model_assignment_id,scope,query_checksum_sha256,status)
            VALUES (?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000g1", 1, 1, "admin_rag_lab", "c" * 64,
                "accepted",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE rag_grounded_requests SET status='completed' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000g1",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM rag_grounded_requests WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000g1",),
        ).fetchone()
        assert row[0] == "completed"


def test_append_only_phase16_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO rag_knowledge_spaces(public_id,name,slug,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000s2",
                "space2", "space2-slug", "00000000-0000-0000-0000-000000000001",
            ),
        )
        space_id = connection.execute(
            "SELECT id FROM rag_knowledge_spaces WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000s2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO rag_knowledge_sources(public_id,knowledge_space_id,source_type,
            title,created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000s3", space_id, "plain_text",
                "title", "00000000-0000-0000-0000-000000000001",
            ),
        )
        source_id = connection.execute(
            "SELECT id FROM rag_knowledge_sources WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000s3",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO rag_source_versions(public_id,knowledge_source_id,version_number,
            content_checksum_sha256,raw_content) VALUES (?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000s4", source_id, 1, "a" * 64, "content",
            ),
        )
        version_id = connection.execute(
            "SELECT id FROM rag_source_versions WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000s4",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO rag_chunk_sets(public_id,source_version_id,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000s5", version_id,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        chunk_set_id = connection.execute(
            "SELECT id FROM rag_chunk_sets WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000s5",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO rag_chunks(public_id,chunk_set_id,source_version_id,sequence_number,
            language,normalized_text,content_checksum_sha256,quality_status)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000s6", chunk_set_id, version_id, 0,
                "en", "hello world", "b" * 64, "accepted",
            ),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE rag_chunks SET quality_status='rejected' WHERE chunk_set_id=?",
                (chunk_set_id,),
            )
