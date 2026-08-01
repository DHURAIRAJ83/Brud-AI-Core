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
    _apply_v21,
    _apply_v22,
    _apply_v23,
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE24_TABLES = {
    "manual_data_records",
    "manual_data_record_revisions",
    "manual_data_reviews",
    "manual_data_verifications",
    "manual_data_usage_decisions",
    "manual_data_events",
}

APPLY_THROUGH_V23 = (
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
    _apply_v21,
    _apply_v22,
    _apply_v23,
)


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def test_fresh_database_reaches_schema_24(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 24
    with database_connection(database) as connection:
        assert PHASE24_TABLES <= _existing_tables(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_23_upgrades_to_24_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v23.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V23:
            apply(connection)
        # A Phase 2 source that predates the Manual Data Studio entirely --
        # must survive untouched and must not gain any implicit manual
        # record link (rule 12/13: existing records are never silently
        # modified or backfilled).
        connection.execute(
            """INSERT INTO data_sources(
                public_id, source_code, title, source_type,
                created_by_admin_public_id, status
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            (
                "00000000-0000-0000-0000-000000000d24",
                "SRC-LEGACY-D24",
                "Legacy pre-Phase-3 source",
                "human_created",
                "legacy-admin",
                "draft",
            ),
        )
        connection.commit()
    assert current_schema_version(database) == 23

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 24
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE24_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        row = connection.execute(
            "SELECT source_code, status FROM data_sources WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000d24",),
        ).fetchone()
        assert row["source_code"] == "SRC-LEGACY-D24"
        assert row["status"] == "draft"
        assert (
            connection.execute("SELECT COUNT(*) FROM manual_data_records").fetchone()[0] == 0
        )


def test_manual_data_records_requires_valid_record_type_and_status(tmp_path: Path) -> None:
    database = tmp_path / "check.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO data_sources(
                public_id, source_code, title, source_type,
                created_by_admin_public_id, status
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            ("src-1", "SRC-D24-0001", "Test source", "human_created", "admin-1", "draft"),
        )
        source_id = connection.execute(
            "SELECT id FROM data_sources WHERE public_id=?", ("src-1",)
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO manual_data_records(
                    public_id, record_code, record_type, source_id, created_by_admin_public_id
                ) VALUES (?, ?, ?, ?, ?)""",
                ("rec-bad", "MD-0001", "not_a_real_type", source_id, "admin-1"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO manual_data_records(
                    public_id, record_code, record_type, status, source_id,
                    created_by_admin_public_id
                ) VALUES (?, ?, ?, ?, ?, ?)""",
                ("rec-bad2", "MD-0002", "plain_text", "not_a_real_status", source_id, "admin-1"),
            )


def test_manual_data_usage_decisions_and_events_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO data_sources(
                public_id, source_code, title, source_type,
                created_by_admin_public_id, status
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            ("src-2", "SRC-D24-0002", "Test source 2", "human_created", "admin-1", "draft"),
        )
        source_id = connection.execute(
            "SELECT id FROM data_sources WHERE public_id=?", ("src-2",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO manual_data_records(
                public_id, record_code, record_type, source_id, created_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?)""",
            ("rec-1", "MD-0003", "plain_text", source_id, "admin-1"),
        )
        record_id = connection.execute(
            "SELECT id FROM manual_data_records WHERE public_id=?", ("rec-1",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO manual_data_record_revisions(
                public_id, record_id, revision_number, input_text, content_hash,
                created_by_admin_public_id
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            ("rev-1", record_id, 1, "hello", "hash1", "admin-1"),
        )
        revision_id = connection.execute(
            "SELECT id FROM manual_data_record_revisions WHERE public_id=?", ("rev-1",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO manual_data_usage_decisions(
                public_id, record_id, revision_id, target_use, allowed, decision_code
            ) VALUES (?, ?, ?, ?, ?, ?)""",
            ("dec-1", record_id, revision_id, "rag", 0, "BLOCKED_RIGHTS_UNKNOWN"),
        )
        connection.execute(
            """INSERT INTO manual_data_events(
                public_id, record_id, event_type, performed_by_admin_public_id
            ) VALUES (?, ?, ?, ?)""",
            ("evt-1", record_id, "record_created", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE manual_data_usage_decisions SET allowed=1 WHERE public_id=?", ("dec-1",)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM manual_data_events WHERE public_id=?", ("evt-1",))
