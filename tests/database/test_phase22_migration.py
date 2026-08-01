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
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE22_COLUMNS = {
    "summary",
    "execution_status",
    "executed_at",
    "execution_result_json",
    "executor_public_id",
}

APPLY_THROUGH_V21 = (
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
)


def test_fresh_database_reaches_schema_22(tmp_path: Path) -> None:
    # A fresh database always reaches the current SCHEMA_VERSION (now beyond
    # 22, as later phases add their own migrations) -- this test only checks
    # that migration 22's own columns exist along the way, not that 22 is
    # the final version.
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 22
    with database_connection(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(admin_approvals)")}
        assert PHASE22_COLUMNS <= columns
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))


def test_schema_21_upgrades_to_22_and_preserves_existing_approvals(tmp_path: Path) -> None:
    database = tmp_path / "v21.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V21:
            apply(connection)
        connection.execute(
            """INSERT INTO admin_approvals(public_id,action_type,target_type,target_public_id,
            requested_by) VALUES (?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-000000000p22",
                "dataset_record_review",
                "dataset_record",
                "target-1",
                "admin-assistant",
            ),
        )
        connection.commit()
    assert current_schema_version(database) == 21

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    # upgrade_database always brings a database to the current SCHEMA_VERSION,
    # not just to 22 -- later phases add their own migrations on top.
    assert version == SCHEMA_VERSION
    assert integrity == "ok"

    with database_connection(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(admin_approvals)")}
        assert PHASE22_COLUMNS <= columns
        row = connection.execute(
            "SELECT status, execution_status, summary FROM admin_approvals WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000p22",),
        ).fetchone()
        assert row["status"] == "pending"
        assert row["execution_status"] == "not_applicable"
        assert row["summary"] == ""
        assert not list(connection.execute("PRAGMA foreign_key_check"))
