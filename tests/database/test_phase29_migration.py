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
    _apply_v24,
    _apply_v25,
    _apply_v26,
    _apply_v27,
    _apply_v28,
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE29_TABLES = {
    "admin_assistant_context_snapshots",
    "admin_assistant_tool_invocations",
    "admin_assistant_feedback",
}

APPLY_THROUGH_V28 = (
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
    _apply_v24,
    _apply_v25,
    _apply_v26,
    _apply_v27,
    _apply_v28,
)


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _insert_approval(connection, public_id: str) -> int:
    connection.execute(
        """INSERT INTO admin_approvals(public_id, action_type, target_type, target_public_id,
        requested_by) VALUES (?,?,?,?,?)""",
        (public_id, "dataset_record_review", "dataset_record", "rec-1", "admin-1"),
    )
    return connection.execute(
        "SELECT id FROM admin_approvals WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_fresh_database_reaches_schema_29(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 29
    with database_connection(database) as connection:
        assert PHASE29_TABLES <= _existing_tables(connection)
        cols = {row[1] for row in connection.execute("PRAGMA table_info(admin_approvals)")}
        assert {"expires_at", "risk_level", "preview_json", "stale_check_json"} <= cols
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_28_upgrades_to_29_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v28.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V28:
            apply(connection)
        _insert_approval(connection, "00000000-0000-0000-0000-000000000a29")
        connection.commit()
    assert current_schema_version(database) == 28

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 29
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE29_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        row = connection.execute(
            "SELECT action_type, risk_level FROM admin_approvals WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000a29",),
        ).fetchone()
        assert row["action_type"] == "dataset_record_review"
        assert row["risk_level"] == "moderate"


def test_existing_admin_approvals_rows_get_sensible_defaults(tmp_path: Path) -> None:
    database = tmp_path / "defaults.db"
    initialize_database(database)
    with database_connection(database) as connection:
        approval_id = _insert_approval(connection, "appr-1")
        connection.commit()
        row = connection.execute(
            "SELECT expires_at, risk_level, preview_json, stale_check_json FROM admin_approvals "
            "WHERE id=?",
            (approval_id,),
        ).fetchone()
        assert row["expires_at"] is None
        assert row["risk_level"] == "moderate"
        assert row["preview_json"] == "{}"
        assert row["stale_check_json"] == "{}"


def test_admin_assistant_tool_invocations_requires_valid_mode_and_status(tmp_path: Path) -> None:
    database = tmp_path / "tools.db"
    initialize_database(database)
    with database_connection(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO admin_assistant_tool_invocations(public_id, tool_name, mode,
                performed_by_admin_public_id) VALUES (?,?,?,?)""",
                ("tool-bad", "get_dashboard_overview", "not_a_real_mode", "admin-1"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO admin_assistant_tool_invocations(public_id, tool_name, status,
                performed_by_admin_public_id) VALUES (?,?,?,?)""",
                ("tool-bad2", "get_dashboard_overview", "not_a_real_status", "admin-1"),
            )
        connection.execute(
            """INSERT INTO admin_assistant_tool_invocations(public_id, tool_name, mode,
            performed_by_admin_public_id) VALUES (?,?,?,?)""",
            ("tool-1", "get_dashboard_overview", "guide", "admin-1"),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM admin_assistant_tool_invocations WHERE public_id=?", ("tool-1",)
        ).fetchone()
        assert row["status"] == "succeeded"
        # Mutable (status/completed_at are updated once the call finishes) but never deletable.
        connection.execute(
            "UPDATE admin_assistant_tool_invocations SET status='failed' WHERE public_id=?",
            ("tool-1",),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM admin_assistant_tool_invocations WHERE public_id=?", ("tool-1",)
            )


def test_admin_assistant_context_snapshots_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "snapshots.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO admin_assistant_context_snapshots(public_id, page_id,
            registry_version, created_by_admin_public_id) VALUES (?,?,?,?)""",
            ("snap-1", "data_overview", "v1", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE admin_assistant_context_snapshots SET page_id='datasets' WHERE public_id=?",
                ("snap-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM admin_assistant_context_snapshots WHERE public_id=?", ("snap-1",)
            )


def test_admin_assistant_feedback_requires_valid_rating_and_is_append_only(
    tmp_path: Path,
) -> None:
    database = tmp_path / "feedback.db"
    initialize_database(database)
    with database_connection(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO admin_assistant_feedback(public_id, rating, registry_version,
                submitted_by_admin_public_id) VALUES (?,?,?,?)""",
                ("fb-bad", "not_a_real_rating", "v1", "admin-1"),
            )
        connection.execute(
            """INSERT INTO admin_assistant_feedback(public_id, rating, registry_version,
            submitted_by_admin_public_id) VALUES (?,?,?,?)""",
            ("fb-1", "helpful", "v1", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE admin_assistant_feedback SET comment='changed' WHERE public_id=?", ("fb-1",)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM admin_assistant_feedback WHERE public_id=?", ("fb-1",))
