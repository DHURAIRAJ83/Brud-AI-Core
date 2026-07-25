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
    current_schema_version,
    initialize_database,
    sha256_file,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE17_TABLES = {
    "conversation_memory_policies",
    "conversation_sessions",
    "conversation_session_participants",
    "conversation_turns",
    "conversation_turn_events",
    "conversation_summaries",
    "conversation_summary_versions",
    "memory_consents",
    "memory_items",
    "memory_item_versions",
    "memory_item_events",
    "memory_embeddings",
    "memory_retrieval_profiles",
    "memory_retrieval_runs",
    "memory_retrieval_results",
    "chat_orchestration_runs",
    "chat_context_assemblies",
    "chat_context_items",
    "chat_grounded_responses",
    "chat_response_citations",
    "chat_orchestration_issues",
    "memory_evaluation_suites",
    "memory_evaluation_fixtures",
    "memory_evaluation_runs",
    "memory_evaluation_metrics",
    "conversation_memory_manifests",
}

APPLY_THROUGH_V16 = (
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
)


def test_fresh_database_reaches_schema_17(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    with database_connection(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert PHASE17_TABLES <= tables
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_migration_016_is_unchanged_in_isolation(tmp_path: Path) -> None:
    """Proves migration 016 still behaves exactly as it did before Phase 17 existed."""
    database = tmp_path / "v16_only.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V16:
            apply(connection)
        connection.commit()
    assert current_schema_version(database) == 16
    with database_connection(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 16
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"rag_knowledge_spaces", "rag_retrieval_profiles"} <= tables
        assert not (PHASE17_TABLES & tables)
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_16_upgrades_to_17(tmp_path: Path) -> None:
    database = tmp_path / "v16.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V16:
            apply(connection)
        connection.execute(
            "INSERT INTO dataset_sources(name,source_type,status,public_id) VALUES (?,?,?,?)",
            ("Preserved Phase16 Row", "manual", "draft", "00000000-0000-0000-0000-000000000098"),
        )
        connection.commit()
    assert current_schema_version(database) == 16
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
        assert PHASE17_TABLES <= tables
        assert {
            "ix_conversation_sessions_participant",
            "ix_memory_items_participant",
            "ix_memory_retrieval_results_run",
        } <= indexes
        assert {
            "conversation_turns_immutable_update",
            "conversation_turn_events_immutable_update",
            "conversation_summary_versions_immutable_update",
            "memory_item_versions_immutable_update",
            "memory_item_events_immutable_update",
            "memory_embeddings_immutable_update",
            "memory_retrieval_runs_immutable_update",
            "memory_retrieval_results_immutable_update",
            "chat_context_assemblies_immutable_update",
            "chat_context_items_immutable_update",
            "chat_orchestration_runs_immutable_update",
            "chat_grounded_responses_immutable_update",
            "chat_response_citations_immutable_update",
            "chat_orchestration_issues_immutable_update",
            "memory_evaluation_fixtures_immutable_update",
            "memory_evaluation_metrics_immutable_update",
            "conversation_memory_manifests_immutable_update",
        } <= triggers
        assert (
            connection.execute("SELECT name FROM dataset_sources").fetchone()[0]
            == "Preserved Phase16 Row"
        )
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_17_upgrade_is_a_no_op(tmp_path: Path) -> None:
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


def test_migration_17_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "idempotent.db"
    initialize_database(database)
    initialize_database(database)
    initialize_database(database)
    with database_connection(database) as connection:
        rows = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations WHERE version = 17"
        ).fetchone()
        assert rows[0] == 1
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_phase17_tables_indexes_and_triggers_are_deterministic(tmp_path: Path) -> None:
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


def test_conversation_and_memory_lifecycle_tables_are_mutable(tmp_path: Path) -> None:
    """policies/sessions/summaries/consents/memory items/retrieval profiles/
    evaluation suites/evaluation runs are lifecycle rows."""

    database = tmp_path / "mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO conversation_memory_policies(public_id,name,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000m1", "policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE conversation_memory_policies SET lifecycle_status='active' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000m1",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT lifecycle_status FROM conversation_memory_policies WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000m1",),
        ).fetchone()
        assert row[0] == "active"


def test_memory_evaluation_runs_are_mutable(tmp_path: Path) -> None:
    """memory_evaluation_runs needs a create(draft)->execute(completed) two-phase
    flow, exactly like Phase 16's rag_evaluation_runs -- deliberately not
    append-only despite the literal spec table list."""

    database = tmp_path / "eval_runs_mutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO memory_evaluation_suites(public_id,name,version,
            created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000e1", "suite", "v1",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        suite_id = connection.execute(
            "SELECT id FROM memory_evaluation_suites WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000e1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO memory_evaluation_runs(public_id,evaluation_suite_id,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000e2", suite_id,
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        connection.commit()
        connection.execute(
            "UPDATE memory_evaluation_runs SET status='completed' WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000e2",),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM memory_evaluation_runs WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000e2",),
        ).fetchone()
        assert row[0] == "completed"


def test_append_only_phase17_tables_reject_updates(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """INSERT INTO conversation_memory_policies(public_id,name,
            created_by_admin_public_id) VALUES (?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000a1", "policy",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        policy_id = connection.execute(
            "SELECT id FROM conversation_memory_policies WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000a1",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO conversation_sessions(public_id,session_mode,memory_policy_id,
            participant_scope_key,created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000a2", "private_no_persist", policy_id,
                "admin:00000000-0000-0000-0000-000000000001",
                "00000000-0000-0000-0000-000000000001",
            ),
        )
        session_id = connection.execute(
            "SELECT id FROM conversation_sessions WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000a2",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO conversation_turns(public_id,session_id,sequence_number,role,
            content_checksum_sha256) VALUES (?,?,?,?,?)""",
            ("00000000-0000-0000-0000-0000000000a3", session_id, 0, "user", "a" * 64),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE conversation_turns SET role='assistant' WHERE session_id=?",
                (session_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM conversation_turns WHERE session_id=?",
                (session_id,),
            )

        request_turn_id = connection.execute(
            "SELECT id FROM conversation_turns WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000a3",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO chat_context_assemblies(public_id,session_id,maximum_model_context,
            final_context_checksum_sha256) VALUES (?,?,?,?)""",
            ("00000000-0000-0000-0000-0000000000a4", session_id, 512, "b" * 64),
        )
        assembly_id = connection.execute(
            "SELECT id FROM chat_context_assemblies WHERE public_id=?",
            ("00000000-0000-0000-0000-0000000000a4",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO chat_orchestration_runs(public_id,session_id,request_turn_id,
            context_assembly_id,status) VALUES (?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-0000000000a5", session_id, request_turn_id,
                assembly_id, "completed",
            ),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE chat_orchestration_runs SET status='generation_failed' WHERE public_id=?",
                ("00000000-0000-0000-0000-0000000000a5",),
            )
