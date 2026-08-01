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
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE23_TABLES = {
    "data_sources",
    "source_rights",
    "source_verification_events",
    "source_usage_decisions",
    "source_record_links",
}

APPLY_THROUGH_V22 = (
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
)


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def test_fresh_database_reaches_schema_23(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 23
    with database_connection(database) as connection:
        assert PHASE23_TABLES <= _existing_tables(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_22_upgrades_to_23_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v22.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V22:
            apply(connection)
        # Legacy row that predates the registry entirely -- must survive
        # untouched and must not gain any implicit source link or rights
        # assertion (rule 6/13: existing records remain readable and are
        # never silently marked as authorized).
        connection.execute(
            "INSERT INTO dataset_sources(public_id, name, source_type, status) VALUES (?, ?, ?, ?)",
            ("00000000-0000-0000-0000-000000000d23", "Legacy source", "manual", "pending"),
        )
        connection.commit()
    assert current_schema_version(database) == 22

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 23
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE23_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

        legacy = connection.execute(
            "SELECT name, status FROM dataset_sources WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000d23",),
        ).fetchone()
        assert legacy["name"] == "Legacy source"
        assert legacy["status"] == "pending"

        # No source_record_links were fabricated for it.
        links = connection.execute(
            "SELECT COUNT(*) FROM source_record_links WHERE entity_public_id=?",
            ("00000000-0000-0000-0000-000000000d23",),
        ).fetchone()[0]
        assert links == 0

        # Registry tables start empty -- no destructive/backfill inserts.
        for table in PHASE23_TABLES:
            count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            assert count == 0


def test_source_rights_requires_a_data_source(tmp_path: Path) -> None:
    database = tmp_path / "fk.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        raised = False
        try:
            connection.execute(
                "INSERT INTO source_rights(public_id, data_source_id) VALUES (?, ?)",
                ("00000000-0000-0000-0000-0000000fake1", 999999),
            )
            connection.commit()
        except Exception:
            raised = True
            connection.rollback()
        assert raised


def test_verification_events_and_usage_decisions_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            "INSERT INTO data_sources(public_id, source_code, title, source_type, "
            "created_by_admin_public_id) VALUES (?, ?, ?, ?, ?)",
            (
                "00000000-0000-0000-0000-00000000ds01",
                "SRC-TEST-0001",
                "Test source",
                "human_created",
                "admin-1",
            ),
        )
        source_id = connection.execute(
            "SELECT id FROM data_sources WHERE public_id=?",
            ("00000000-0000-0000-0000-00000000ds01",),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO source_verification_events(public_id, data_source_id, action, "
            "verification_status_after, performed_by_admin_public_id) VALUES (?, ?, ?, ?, ?)",
            (
                "00000000-0000-0000-0000-00000000ve01",
                source_id,
                "self_declare",
                "self_declared",
                "admin-1",
            ),
        )
        connection.execute(
            "INSERT INTO source_usage_decisions(public_id, data_source_id, target_use, "
            "allowed, decision_code) VALUES (?, ?, ?, ?, ?)",
            ("00000000-0000-0000-0000-00000000ud01", source_id, "rag", 0, "BLOCKED_RIGHTS_UNKNOWN"),
        )
        connection.commit()

        for table, column in [
            ("source_verification_events", "notes"),
            ("source_usage_decisions", "decision_code"),
        ]:
            blocked = False
            try:
                connection.execute(f"UPDATE {table} SET {column} = 'changed'")  # noqa: S608
                connection.commit()
            except Exception:
                blocked = True
                connection.rollback()
            assert blocked, f"{table} should reject UPDATE"

            blocked = False
            try:
                connection.execute(f"DELETE FROM {table}")  # noqa: S608
                connection.commit()
            except Exception:
                blocked = True
                connection.rollback()
            assert blocked, f"{table} should reject DELETE"


def test_source_record_links_can_be_deleted_unlike_the_append_only_tables(tmp_path: Path) -> None:
    database = tmp_path / "links.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            "INSERT INTO data_sources(public_id, source_code, title, source_type, "
            "created_by_admin_public_id) VALUES (?, ?, ?, ?, ?)",
            (
                "00000000-0000-0000-0000-00000000ds02",
                "SRC-TEST-0002",
                "Test source 2",
                "human_created",
                "admin-1",
            ),
        )
        source_id = connection.execute(
            "SELECT id FROM data_sources WHERE public_id=?",
            ("00000000-0000-0000-0000-00000000ds02",),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO source_record_links(public_id, data_source_id, entity_type, "
            "entity_public_id, created_by_admin_public_id) VALUES (?, ?, ?, ?, ?)",
            (
                "00000000-0000-0000-0000-00000000sl01",
                source_id,
                "dataset_record",
                "record-1",
                "admin-1",
            ),
        )
        connection.commit()
        connection.execute(
            "DELETE FROM source_record_links WHERE public_id=?",
            ("00000000-0000-0000-0000-00000000sl01",),
        )
        connection.commit()
        remaining = connection.execute("SELECT COUNT(*) FROM source_record_links").fetchone()[0]
        assert remaining == 0
