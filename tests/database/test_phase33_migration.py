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
    _apply_v32,
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE33_TABLES = {
    "external_dataset_verification_cases",
    "external_dataset_evidence_snapshots",
    "external_dataset_evidence_links",
    "external_dataset_identity_checks",
    "external_dataset_permission_assessments",
    "external_dataset_verification_reviews",
    "external_dataset_verification_events",
    "external_dataset_withdrawal_notices",
    "external_dataset_upstream_sources",
}

APPLY_THROUGH_V32 = (
    _apply_v1, _apply_v2, _apply_v3, _apply_v4, _apply_v5, _apply_v6, _apply_v7, _apply_v8,
    _apply_v9, _apply_v10, _apply_v11, _apply_v12, _apply_v13, _apply_v14, _apply_v15,
    _apply_v16, _apply_v17, _apply_v18, _apply_v19, _apply_v20, _apply_v21, _apply_v22,
    _apply_v23, _apply_v24, _apply_v25, _apply_v26, _apply_v27, _apply_v28, _apply_v29,
    _apply_v30, _apply_v31, _apply_v32,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _insert_session(connection, public_id="sess-1", session_code="session-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_search_sessions(public_id, session_code,
        requested_by_admin_public_id) VALUES (?,?,?)""",
        (public_id, session_code, ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_search_sessions WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_candidate(connection, session_id, public_id="cand-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_candidates(public_id, search_session_id,
        canonical_name, normalized_name) VALUES (?,?,?,?)""",
        (public_id, session_id, "Tamil Corpus", "tamil corpus"),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_candidates WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_case(connection, candidate_id, session_id, public_id="case-1", code="VC-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_verification_cases(public_id, verification_code,
        candidate_id, search_session_id, requested_by_admin_public_id)
        VALUES (?,?,?,?,?)""",
        (public_id, code, candidate_id, session_id, ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_verification_cases WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_evidence_snapshot(connection, case_id, candidate_id, public_id="ev-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_evidence_snapshots(public_id, verification_case_id,
        candidate_id, evidence_type, authority_level, content_type, content_checksum,
        created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?)""",
        (public_id, case_id, candidate_id, "licence_file", "primary", "text/plain",
         "a" * 64, ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_evidence_snapshots WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _setup_case(connection) -> tuple[int, int, int]:
    session_id = _insert_session(connection)
    candidate_id = _insert_candidate(connection, session_id)
    case_id = _insert_case(connection, candidate_id, session_id)
    return session_id, candidate_id, case_id


def test_fresh_database_reaches_schema_33(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 33
    with database_connection(database) as connection:
        assert PHASE33_TABLES <= _existing_tables(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_32_upgrades_to_33_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v32.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V32:
            apply(connection)
        connection.execute(
            """INSERT INTO external_dataset_search_sessions(public_id, session_code,
            requested_by_admin_public_id) VALUES (?,?,?)""",
            ("sess-preexisting", "preexisting-code", ADMIN_ID),
        )
        connection.commit()
    assert current_schema_version(database) == 32

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 33
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE33_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        preserved = connection.execute(
            "SELECT session_code FROM external_dataset_search_sessions WHERE public_id=?",
            ("sess-preexisting",),
        ).fetchone()
        assert preserved["session_code"] == "preexisting-code"

        _session_id, candidate_id, case_id = _setup_case(connection)
        connection.commit()
        row = connection.execute(
            "SELECT status, identity_status FROM external_dataset_verification_cases WHERE id=?",
            (case_id,),
        ).fetchone()
        assert row["status"] == "draft"
        assert row["identity_status"] == "not_verified"
        assert candidate_id


def test_verification_code_is_unique(tmp_path: Path) -> None:
    database = tmp_path / "unique.db"
    initialize_database(database)
    with database_connection(database) as connection:
        session_id, candidate_id, _case_id = _setup_case(connection)
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_verification_cases(public_id, verification_code,
                candidate_id, search_session_id, requested_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                ("case-dup", "VC-1", candidate_id, session_id, ADMIN_ID),
            )


def test_case_rejects_unknown_status(tmp_path: Path) -> None:
    database = tmp_path / "checks.db"
    initialize_database(database)
    with database_connection(database) as connection:
        session_id, candidate_id, _case_id = _setup_case(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_verification_cases(public_id, verification_code,
                candidate_id, search_session_id, requested_by_admin_public_id, status)
                VALUES (?,?,?,?,?,?)""",
                ("case-bad", "VC-bad", candidate_id, session_id, ADMIN_ID, "not_a_real_status"),
            )


def test_evidence_snapshots_reject_unknown_evidence_type(tmp_path: Path) -> None:
    database = tmp_path / "evidence_checks.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_evidence_snapshots(public_id,
                verification_case_id, candidate_id, evidence_type, authority_level,
                content_type, content_checksum, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                ("ev-bad", case_id, candidate_id, "not_a_real_type", "primary",
                 "text/plain", "a" * 64, ADMIN_ID),
            )


def test_evidence_snapshots_are_never_deleted_but_may_be_updated(tmp_path: Path) -> None:
    database = tmp_path / "no_delete.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        evidence_id = _insert_evidence_snapshot(connection, case_id, candidate_id)
        connection.commit()

        connection.execute(
            "UPDATE external_dataset_evidence_snapshots SET is_current = 0 WHERE id = ?",
            (evidence_id,),
        )
        connection.commit()
        row = connection.execute(
            "SELECT is_current FROM external_dataset_evidence_snapshots WHERE id = ?",
            (evidence_id,),
        ).fetchone()
        assert row["is_current"] == 0

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_evidence_snapshots WHERE id = ?", (evidence_id,)
            )


def test_permission_assessments_are_unique_per_case_and_type(tmp_path: Path) -> None:
    database = tmp_path / "perm_unique.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        connection.execute(
            """INSERT INTO external_dataset_permission_assessments(public_id,
            verification_case_id, candidate_id, permission_type)
            VALUES (?,?,?,?)""",
            ("perm-1", case_id, candidate_id, "training_use"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_permission_assessments(public_id,
                verification_case_id, candidate_id, permission_type)
                VALUES (?,?,?,?)""",
                ("perm-2", case_id, candidate_id, "training_use"),
            )


def test_automated_permission_status_never_requires_reviewer(tmp_path: Path) -> None:
    database = tmp_path / "perm_automated.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        connection.execute(
            """INSERT INTO external_dataset_permission_assessments(public_id,
            verification_case_id, candidate_id, permission_type, status)
            VALUES (?,?,?,?,?)""",
            ("perm-auto", case_id, candidate_id, "training_use", "needs_legal_review"),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM external_dataset_permission_assessments WHERE public_id=?",
            ("perm-auto",),
        ).fetchone()
        assert row["status"] == "needs_legal_review"


def test_admin_only_permission_status_requires_reviewer_and_reason(tmp_path: Path) -> None:
    database = tmp_path / "perm_admin_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_permission_assessments(public_id,
                verification_case_id, candidate_id, permission_type, status)
                VALUES (?,?,?,?,?)""",
                ("perm-bad", case_id, candidate_id, "training_use", "approved"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_permission_assessments(public_id,
                verification_case_id, candidate_id, permission_type, status,
                reviewed_by, reviewed_at)
                VALUES (?,?,?,?,?,?,?)""",
                ("perm-bad2", case_id, candidate_id, "training_use", "approved",
                 REVIEWER_ID, "2026-01-01T00:00:00"),
            )


def test_admin_only_permission_status_succeeds_with_full_review_fields(tmp_path: Path) -> None:
    database = tmp_path / "perm_admin_ok.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        connection.execute(
            """INSERT INTO external_dataset_permission_assessments(public_id,
            verification_case_id, candidate_id, permission_type, status,
            reviewed_by, reviewed_at, reason)
            VALUES (?,?,?,?,?,?,?,?)""",
            ("perm-good", case_id, candidate_id, "training_use", "approved",
             REVIEWER_ID, "2026-01-01T00:00:00", "Evidence-backed licence review"),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status, reviewed_by FROM external_dataset_permission_assessments "
            "WHERE public_id=?",
            ("perm-good",),
        ).fetchone()
        assert row["status"] == "approved"
        assert row["reviewed_by"] == REVIEWER_ID


def test_admin_only_permission_status_cannot_be_set_via_update_either(tmp_path: Path) -> None:
    database = tmp_path / "perm_admin_update.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        connection.execute(
            """INSERT INTO external_dataset_permission_assessments(public_id,
            verification_case_id, candidate_id, permission_type)
            VALUES (?,?,?,?)""",
            ("perm-update", case_id, candidate_id, "commercial_use"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE external_dataset_permission_assessments SET status='prohibited' "
                "WHERE public_id=?",
                ("perm-update",),
            )


def test_verification_reviews_require_nonempty_reason(tmp_path: Path) -> None:
    database = tmp_path / "reviews_reason.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_verification_reviews(public_id,
                verification_case_id, decision, reason, reviewer_admin_public_id)
                VALUES (?,?,?,?,?)""",
                ("review-bad", case_id, "approved", "   ", REVIEWER_ID),
            )


def test_verification_reviews_events_and_withdrawal_notices_are_append_only(
    tmp_path: Path,
) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        connection.execute(
            """INSERT INTO external_dataset_verification_reviews(public_id,
            verification_case_id, decision, reason, reviewer_admin_public_id)
            VALUES (?,?,?,?,?)""",
            ("review-1", case_id, "approved", "Licence file confirms CC-BY-4.0", REVIEWER_ID),
        )
        connection.execute(
            """INSERT INTO external_dataset_verification_events(public_id,
            verification_case_id, event_type, performed_by_admin_public_id)
            VALUES (?,?,?,?)""",
            ("event-1", case_id, "case_created", ADMIN_ID),
        )
        connection.execute(
            """INSERT INTO external_dataset_withdrawal_notices(public_id,
            verification_case_id, candidate_id, notice_type, recorded_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            ("notice-1", case_id, candidate_id, "licence_changed", ADMIN_ID),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE external_dataset_verification_reviews SET reason='changed' "
                "WHERE public_id=?",
                ("review-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_verification_reviews WHERE public_id=?",
                ("review-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE external_dataset_verification_events SET summary='changed' "
                "WHERE public_id=?",
                ("event-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_verification_events WHERE public_id=?",
                ("event-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE external_dataset_withdrawal_notices SET notice_text='changed' "
                "WHERE public_id=?",
                ("notice-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_withdrawal_notices WHERE public_id=?",
                ("notice-1",),
            )


def test_conflict_detected_event_carries_severity_and_resolution_columns(
    tmp_path: Path,
) -> None:
    database = tmp_path / "conflict_event.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        connection.execute(
            """INSERT INTO external_dataset_verification_events(public_id,
            verification_case_id, event_type, conflict_type, conflict_severity,
            resolution_status, performed_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?)""",
            ("event-conflict", case_id, "conflict_detected", "declared_vs_licence_file",
             "blocking", "unresolved", ADMIN_ID),
        )
        connection.commit()
        row = connection.execute(
            "SELECT conflict_severity, resolution_status FROM external_dataset_verification_"
            "events WHERE public_id=?",
            ("event-conflict",),
        ).fetchone()
        assert row["conflict_severity"] == "blocking"
        assert row["resolution_status"] == "unresolved"


def test_evidence_links_are_unique_per_snapshot_entity_and_role(tmp_path: Path) -> None:
    database = tmp_path / "evidence_links.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        evidence_id = _insert_evidence_snapshot(connection, case_id, candidate_id)
        connection.execute(
            """INSERT INTO external_dataset_evidence_links(public_id, evidence_snapshot_id,
            linked_entity_type, linked_entity_id, link_role) VALUES (?,?,?,?,?)""",
            ("link-1", evidence_id, "identity_check", 1, "supports"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_evidence_links(public_id, evidence_snapshot_id,
                linked_entity_type, linked_entity_id, link_role) VALUES (?,?,?,?,?)""",
                ("link-2", evidence_id, "identity_check", 1, "supports"),
            )


def test_upstream_sources_reject_unknown_relationship_type(tmp_path: Path) -> None:
    database = tmp_path / "upstream_checks.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_upstream_sources(public_id,
                verification_case_id, candidate_id, upstream_name, relationship_type,
                created_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
                ("up-bad", case_id, candidate_id, "Some Corpus", "not_a_real_relationship",
                 ADMIN_ID),
            )


def test_case_with_evidence_can_never_be_deleted(tmp_path: Path) -> None:
    # `ON DELETE CASCADE` on evidence_snapshots is declarative only --
    # evidence_snapshots' own BEFORE DELETE trigger fires even for an
    # implicit cascade delete and aborts the whole statement, so a case
    # that has collected any evidence can never be deleted, only ever
    # cancelled/expired/withdrawn via its own status column. This
    # mirrors Phase 10's own "nothing is truly deleted" guarantee.
    database = tmp_path / "cascade.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        evidence_id = _insert_evidence_snapshot(connection, case_id, candidate_id)
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_verification_cases WHERE id = ?", (case_id,)
            )
        remaining = connection.execute(
            "SELECT 1 FROM external_dataset_evidence_snapshots WHERE id = ?", (evidence_id,)
        ).fetchone()
        assert remaining is not None
