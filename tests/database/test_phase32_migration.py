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
    _apply_v29,
    _apply_v30,
    _apply_v31,
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

APPLY_THROUGH_V31 = (
    _apply_v1, _apply_v2, _apply_v3, _apply_v4, _apply_v5, _apply_v6, _apply_v7, _apply_v8,
    _apply_v9, _apply_v10, _apply_v11, _apply_v12, _apply_v13, _apply_v14, _apply_v15,
    _apply_v16, _apply_v17, _apply_v18, _apply_v19, _apply_v20, _apply_v21, _apply_v22,
    _apply_v23, _apply_v24, _apply_v25, _apply_v26, _apply_v27, _apply_v28, _apply_v29,
    _apply_v30, _apply_v31,
)


def _insert_admin(connection, public_id: str, username: str) -> int:
    connection.execute(
        """INSERT INTO admin_accounts(public_id, username, display_name, password_hash)
        VALUES (?,?,?,?)""",
        (public_id, username, username, "hash"),
    )
    return connection.execute(
        "SELECT id FROM admin_accounts WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_fresh_database_reaches_schema_32(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 32
    with database_connection(database) as connection:
        cols = {row[1] for row in connection.execute("PRAGMA table_info(admin_accounts)")}
        assert "admin_assistant_response_language" in cols
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_31_upgrades_to_32_and_preserves_existing_admins(tmp_path: Path) -> None:
    database = tmp_path / "v31.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V31:
            apply(connection)
        _insert_admin(connection, "00000000-0000-0000-0000-000000000a32", "phase10a-existing")
        connection.commit()
    assert current_schema_version(database) == 31

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 32
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        row = connection.execute(
            "SELECT username, admin_assistant_response_language FROM admin_accounts "
            "WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000a32",),
        ).fetchone()
        assert row["username"] == "phase10a-existing"
        assert row["admin_assistant_response_language"] == "auto"


def test_new_admin_defaults_to_auto(tmp_path: Path) -> None:
    database = tmp_path / "defaults.db"
    initialize_database(database)
    with database_connection(database) as connection:
        admin_id = _insert_admin(connection, "admin-1", "someone")
        connection.commit()
        row = connection.execute(
            "SELECT admin_assistant_response_language FROM admin_accounts WHERE id=?", (admin_id,)
        ).fetchone()
        assert row["admin_assistant_response_language"] == "auto"


def test_admin_assistant_response_language_rejects_invalid_enum(tmp_path: Path) -> None:
    database = tmp_path / "invalid.db"
    initialize_database(database)
    with database_connection(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO admin_accounts(public_id, username, display_name, password_hash,
                admin_assistant_response_language) VALUES (?,?,?,?,?)""",
                ("admin-bad", "bad", "bad", "hash", "klingon"),
            )
        connection.execute(
            """INSERT INTO admin_accounts(public_id, username, display_name, password_hash,
            admin_assistant_response_language) VALUES (?,?,?,?,?)""",
            ("admin-good", "good", "good", "hash", "tanglish"),
        )
        connection.commit()
        row = connection.execute(
            "SELECT admin_assistant_response_language FROM admin_accounts WHERE public_id=?",
            ("admin-good",),
        ).fetchone()
        assert row["admin_assistant_response_language"] == "tanglish"
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE admin_accounts SET admin_assistant_response_language='klingon' "
                "WHERE public_id=?",
                ("admin-good",),
            )


def test_all_four_response_language_values_accepted(tmp_path: Path) -> None:
    database = tmp_path / "values.db"
    initialize_database(database)
    with database_connection(database) as connection:
        for index, value in enumerate(("tamil", "english", "tanglish", "auto")):
            connection.execute(
                """INSERT INTO admin_accounts(public_id, username, display_name, password_hash,
                admin_assistant_response_language) VALUES (?,?,?,?,?)""",
                (f"admin-{index}", f"user{index}", f"user{index}", "hash", value),
            )
        connection.commit()
        rows = connection.execute(
            "SELECT admin_assistant_response_language FROM admin_accounts ORDER BY public_id"
        ).fetchall()
        assert [row[0] for row in rows] == ["tamil", "english", "tanglish", "auto"]
