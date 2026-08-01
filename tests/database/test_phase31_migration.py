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
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE31_TABLES = {
    "external_dataset_search_sessions",
    "external_dataset_search_requirements",
    "external_dataset_search_provider_runs",
    "external_dataset_candidates",
    "external_dataset_candidate_sources",
    "external_dataset_candidate_scores",
    "external_dataset_candidate_comparisons",
    "external_dataset_search_events",
}

APPLY_THROUGH_V30 = (
    _apply_v1, _apply_v2, _apply_v3, _apply_v4, _apply_v5, _apply_v6, _apply_v7, _apply_v8,
    _apply_v9, _apply_v10, _apply_v11, _apply_v12, _apply_v13, _apply_v14, _apply_v15,
    _apply_v16, _apply_v17, _apply_v18, _apply_v19, _apply_v20, _apply_v21, _apply_v22,
    _apply_v23, _apply_v24, _apply_v25, _apply_v26, _apply_v27, _apply_v28, _apply_v29,
    _apply_v30,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _insert_provider(connection, public_id="prov-1", provider_code="test-provider") -> int:
    connection.execute(
        """INSERT INTO external_data_providers(public_id, provider_code, name, provider_type,
        access_mode, created_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
        (public_id, provider_code, "Test Provider", "public_api", "public", ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM external_data_providers WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_session(connection, public_id="sess-1", session_code="session-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_search_sessions(public_id, session_code,
        requested_by_admin_public_id) VALUES (?,?,?)""",
        (public_id, session_code, ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_search_sessions WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_fresh_database_reaches_schema_31(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 31
    with database_connection(database) as connection:
        assert PHASE31_TABLES <= _existing_tables(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_30_upgrades_to_31_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v30.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V30:
            apply(connection)
        _insert_provider(connection, "prov-preexisting", "preexisting-code")
        connection.commit()
    assert current_schema_version(database) == 30

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 31
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE31_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        preserved = connection.execute(
            "SELECT provider_code FROM external_data_providers WHERE public_id=?",
            ("prov-preexisting",),
        ).fetchone()
        assert preserved["provider_code"] == "preexisting-code"

        session_id = _insert_session(connection, "sess-post-upgrade", "post-upgrade-session")
        connection.commit()
        row = connection.execute(
            "SELECT status, current_stage FROM external_dataset_search_sessions WHERE id=?",
            (session_id,),
        ).fetchone()
        assert row["status"] == "draft"
        assert row["current_stage"] == "requirement"


def test_session_code_is_unique(tmp_path: Path) -> None:
    database = tmp_path / "unique.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _insert_session(connection, "s1", "dup-code")
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_search_sessions(public_id, session_code,
                requested_by_admin_public_id) VALUES (?,?,?)""",
                ("s2", "dup-code", ADMIN_ID),
            )


def test_session_rejects_unknown_status(tmp_path: Path) -> None:
    database = tmp_path / "checks.db"
    initialize_database(database)
    with database_connection(database) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_search_sessions(public_id, session_code,
                requested_by_admin_public_id, status) VALUES (?,?,?,?)""",
                ("s-bad", "bad-code", ADMIN_ID, "not_a_real_status"),
            )


def test_sessions_and_provider_runs_and_candidates_and_sources_are_never_deleted(
    tmp_path: Path,
) -> None:
    database = tmp_path / "no_delete.db"
    initialize_database(database)
    with database_connection(database) as connection:
        session_id = _insert_session(connection)
        provider_id = _insert_provider(connection)
        connection.execute(
            """INSERT INTO external_dataset_search_provider_runs(public_id, search_session_id,
            provider_id, status) VALUES (?,?,?,?)""",
            ("run-1", session_id, provider_id, "success"),
        )
        connection.execute(
            """INSERT INTO external_dataset_candidates(public_id, search_session_id,
            canonical_name, normalized_name) VALUES (?,?,?,?)""",
            ("cand-1", session_id, "Tamil Corpus", "tamil corpus"),
        )
        candidate_id = connection.execute(
            "SELECT id FROM external_dataset_candidates WHERE public_id=?", ("cand-1",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO external_dataset_candidate_sources(public_id, candidate_id,
            provider_id, provider_dataset_id) VALUES (?,?,?,?)""",
            ("src-1", candidate_id, provider_id, "ds-1"),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_search_sessions WHERE public_id=?", ("sess-1",)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_search_provider_runs WHERE public_id=?", ("run-1",)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_candidates WHERE public_id=?", ("cand-1",)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_candidate_sources WHERE public_id=?", ("src-1",)
            )


def test_candidates_default_to_never_approved_use_statuses(tmp_path: Path) -> None:
    database = tmp_path / "defaults.db"
    initialize_database(database)
    with database_connection(database) as connection:
        session_id = _insert_session(connection)
        connection.execute(
            """INSERT INTO external_dataset_candidates(public_id, search_session_id,
            canonical_name, normalized_name) VALUES (?,?,?,?)""",
            ("cand-defaults", session_id, "Tamil Corpus", "tamil corpus"),
        )
        connection.commit()
        row = connection.execute(
            """SELECT licence_status, commercial_use_status, training_use_status,
            rag_use_status, evaluation_use_status FROM external_dataset_candidates
            WHERE public_id=?""",
            ("cand-defaults",),
        ).fetchone()
        assert row["licence_status"] == "unknown"
        assert row["commercial_use_status"] == "unknown"
        assert row["training_use_status"] == "not_approved"
        assert row["rag_use_status"] == "not_approved"
        assert row["evaluation_use_status"] == "not_approved"


def test_candidate_use_status_can_never_become_approved(tmp_path: Path) -> None:
    database = tmp_path / "cannot_approve.db"
    initialize_database(database)
    with database_connection(database) as connection:
        session_id = _insert_session(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_candidates(public_id, search_session_id,
                canonical_name, normalized_name, training_use_status)
                VALUES (?,?,?,?,?)""",
                ("cand-bad", session_id, "X", "x", "approved"),
            )


def test_candidate_scores_upsert_per_dimension(tmp_path: Path) -> None:
    database = tmp_path / "scores.db"
    initialize_database(database)
    with database_connection(database) as connection:
        session_id = _insert_session(connection)
        connection.execute(
            """INSERT INTO external_dataset_candidates(public_id, search_session_id,
            canonical_name, normalized_name) VALUES (?,?,?,?)""",
            ("cand-1", session_id, "X", "x"),
        )
        candidate_id = connection.execute(
            "SELECT id FROM external_dataset_candidates WHERE public_id=?", ("cand-1",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO external_dataset_candidate_scores(public_id, candidate_id, dimension,
            raw_value, weight, score, reason) VALUES (?,?,?,?,?,?,?)""",
            ("score-1", candidate_id, "language_fit", 1.0, 1.5, 1.5, "match"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_candidate_scores(public_id, candidate_id,
                dimension, raw_value, weight, score, reason) VALUES (?,?,?,?,?,?,?)""",
                ("score-2", candidate_id, "language_fit", 0.5, 1.5, 0.75, "different run"),
            )


def test_search_events_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "events.db"
    initialize_database(database)
    with database_connection(database) as connection:
        session_id = _insert_session(connection)
        connection.execute(
            """INSERT INTO external_dataset_search_events(public_id, search_session_id,
            event_type, performed_by_admin_public_id) VALUES (?,?,?,?)""",
            ("event-1", session_id, "session_created", ADMIN_ID),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE external_dataset_search_events SET summary='changed' WHERE public_id=?",
                ("event-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_search_events WHERE public_id=?", ("event-1",)
            )


def test_requirements_are_one_to_one_with_session(tmp_path: Path) -> None:
    database = tmp_path / "requirements.db"
    initialize_database(database)
    with database_connection(database) as connection:
        session_id = _insert_session(connection)
        connection.execute(
            """INSERT INTO external_dataset_search_requirements(public_id, search_session_id)
            VALUES (?,?)""",
            ("req-1", session_id),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_search_requirements(public_id, search_session_id)
                VALUES (?,?)""",
                ("req-2", session_id),
            )
