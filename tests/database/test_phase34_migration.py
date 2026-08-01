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
    _apply_v23,
    _apply_v24,
    _apply_v25,
    _apply_v26,
    _apply_v27,
    _apply_v28,
    _apply_v29,
    _apply_v30,
    _apply_v31,
    _apply_v32,
    _apply_v33,
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

ADMIN_ID = "00000000-0000-0000-0000-000000000001"

APPLY_THROUGH_V33 = (
    _apply_v1, _apply_v2, _apply_v3, _apply_v4, _apply_v5, _apply_v6, _apply_v7, _apply_v8,
    _apply_v9, _apply_v10, _apply_v11, _apply_v12, _apply_v13, _apply_v14, _apply_v15,
    _apply_v16, _apply_v17, _apply_v18, _apply_v19, _apply_v20, _apply_v21, _apply_v22,
    _apply_v23, _apply_v24, _apply_v25, _apply_v26, _apply_v27, _apply_v28, _apply_v29,
    _apply_v30, _apply_v31, _apply_v32, _apply_v33,
)


def _insert_pre_migration_session_candidate_case(connection, case_public_id="case-1") -> None:
    """Inserts a case the way it would have looked *before* migration
    034 ran -- schema 33 has no `declared_licence`/
    `normalized_licence_identifier` columns on this table yet, so a
    pre-existing case row genuinely has neither."""

    connection.execute(
        """INSERT INTO external_dataset_search_sessions(public_id, session_code,
        requested_by_admin_public_id) VALUES (?,?,?)""",
        ("sess-1", "session-code-1", ADMIN_ID),
    )
    connection.execute(
        """INSERT INTO external_dataset_candidates(public_id, search_session_id,
        canonical_name, normalized_name, declared_licence) VALUES (
        ?, (SELECT id FROM external_dataset_search_sessions WHERE public_id='sess-1'), ?,?,?)""",
        ("cand-1", "Tamil Corpus", "tamil corpus", "CC-BY-4.0"),
    )
    connection.execute(
        """INSERT INTO external_dataset_verification_cases(public_id, verification_code,
        candidate_id, requested_by_admin_public_id) VALUES (
        ?, ?, (SELECT id FROM external_dataset_candidates WHERE public_id='cand-1'), ?)""",
        (case_public_id, "VC-1", ADMIN_ID),
    )


def test_fresh_database_reaches_schema_34(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 34
    with database_connection(database) as connection:
        cols = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(external_dataset_verification_cases)"
            )
        }
        assert "declared_licence" in cols
        assert "normalized_licence_identifier" in cols
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_33_upgrades_to_34_and_preserves_existing_cases(tmp_path: Path) -> None:
    database = tmp_path / "v33.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V33:
            apply(connection)
        _insert_pre_migration_session_candidate_case(connection)
        connection.commit()
    assert current_schema_version(database) == 33

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 34
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        row = connection.execute(
            "SELECT verification_code, declared_licence, normalized_licence_identifier "
            "FROM external_dataset_verification_cases WHERE public_id=?",
            ("case-1",),
        ).fetchone()
        assert row["verification_code"] == "VC-1"
        assert row["declared_licence"] is None
        assert row["normalized_licence_identifier"] is None


def test_case_licence_columns_are_freely_writable_post_migration(tmp_path: Path) -> None:
    database = tmp_path / "writable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO external_dataset_search_sessions(public_id, session_code,
            requested_by_admin_public_id) VALUES (?,?,?)""",
            ("sess-3", "session-code-3", ADMIN_ID),
        )
        connection.execute(
            """INSERT INTO external_dataset_candidates(public_id, search_session_id,
            canonical_name, normalized_name) VALUES (
            ?, (SELECT id FROM external_dataset_search_sessions WHERE public_id='sess-3'), ?,?)""",
            ("cand-3", "Tamil ASR", "tamil asr"),
        )
        connection.execute(
            """INSERT INTO external_dataset_verification_cases(public_id, verification_code,
            candidate_id, requested_by_admin_public_id, declared_licence,
            normalized_licence_identifier) VALUES (
            ?, ?,
            (SELECT id FROM external_dataset_candidates WHERE public_id='cand-3'), ?, ?, ?)""",
            ("case-3", "VC-3", ADMIN_ID, "CC-BY 4.0", "CC-BY-4.0"),
        )
        connection.commit()
        row = connection.execute(
            "SELECT declared_licence, normalized_licence_identifier "
            "FROM external_dataset_verification_cases WHERE public_id=?",
            ("case-3",),
        ).fetchone()
        assert row["declared_licence"] == "CC-BY 4.0"
        assert row["normalized_licence_identifier"] == "CC-BY-4.0"


def test_new_case_licence_columns_default_to_null(tmp_path: Path) -> None:
    database = tmp_path / "defaults.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO external_dataset_search_sessions(public_id, session_code,
            requested_by_admin_public_id) VALUES (?,?,?)""",
            ("sess-2", "session-code-2", ADMIN_ID),
        )
        connection.execute(
            """INSERT INTO external_dataset_candidates(public_id, search_session_id,
            canonical_name, normalized_name) VALUES (
            ?, (SELECT id FROM external_dataset_search_sessions WHERE public_id='sess-2'), ?,?)""",
            ("cand-2", "Some Corpus", "some corpus"),
        )
        connection.execute(
            """INSERT INTO external_dataset_verification_cases(public_id, verification_code,
            candidate_id, requested_by_admin_public_id) VALUES (
            ?, ?, (SELECT id FROM external_dataset_candidates WHERE public_id='cand-2'), ?)""",
            ("case-2", "VC-2", ADMIN_ID),
        )
        connection.commit()
        row = connection.execute(
            "SELECT declared_licence, normalized_licence_identifier "
            "FROM external_dataset_verification_cases WHERE public_id=?",
            ("case-2",),
        ).fetchone()
        assert row["declared_licence"] is None
        assert row["normalized_licence_identifier"] is None
