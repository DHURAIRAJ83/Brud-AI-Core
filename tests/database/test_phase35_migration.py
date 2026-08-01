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
    _apply_v33,
    _apply_v34,
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE35_TABLES = {
    "external_dataset_sample_imports",
    "external_dataset_sample_import_approvals",
    "external_dataset_sample_files",
    "external_dataset_sample_download_events",
    "external_dataset_sample_extraction_events",
    "external_dataset_sample_scan_results",
    "external_dataset_sample_records",
    "external_dataset_sample_record_issues",
    "external_dataset_sample_reviews",
    "external_dataset_sample_reports",
    "external_dataset_sample_events",
    "external_dataset_sample_deletion_requests",
}

APPLY_THROUGH_V34 = (
    _apply_v1, _apply_v2, _apply_v3, _apply_v4, _apply_v5, _apply_v6, _apply_v7, _apply_v8,
    _apply_v9, _apply_v10, _apply_v11, _apply_v12, _apply_v13, _apply_v14, _apply_v15,
    _apply_v16, _apply_v17, _apply_v18, _apply_v19, _apply_v20, _apply_v21, _apply_v22,
    _apply_v23, _apply_v24, _apply_v25, _apply_v26, _apply_v27, _apply_v28, _apply_v29,
    _apply_v30, _apply_v31, _apply_v32, _apply_v33, _apply_v34,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _setup_case(connection) -> tuple[int, int, int]:
    connection.execute(
        """INSERT INTO external_dataset_search_sessions(public_id, session_code,
        requested_by_admin_public_id) VALUES (?,?,?)""",
        ("sess-1", "session-1", ADMIN_ID),
    )
    session_id = connection.execute(
        "SELECT id FROM external_dataset_search_sessions WHERE public_id=?", ("sess-1",)
    ).fetchone()[0]
    connection.execute(
        """INSERT INTO external_dataset_candidates(public_id, search_session_id,
        canonical_name, normalized_name) VALUES (?,?,?,?)""",
        ("cand-1", session_id, "Tamil Corpus", "tamil corpus"),
    )
    candidate_id = connection.execute(
        "SELECT id FROM external_dataset_candidates WHERE public_id=?", ("cand-1",)
    ).fetchone()[0]
    connection.execute(
        """INSERT INTO external_dataset_verification_cases(public_id, verification_code,
        candidate_id, search_session_id, requested_by_admin_public_id, locked_at)
        VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)""",
        ("case-1", "VC-1", candidate_id, session_id, ADMIN_ID),
    )
    case_id = connection.execute(
        "SELECT id FROM external_dataset_verification_cases WHERE public_id=?", ("case-1",)
    ).fetchone()[0]
    return session_id, candidate_id, case_id


def _insert_sample_import(connection, case_id, candidate_id, public_id="sample-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_sample_imports(public_id, sample_import_code,
        verification_case_id, candidate_id, purpose, selection_method,
        requested_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
        (public_id, f"SI-{public_id}", case_id, candidate_id, "manual_review",
         "deterministic_first_n", ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_sample_imports WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_approval(
    connection, sample_import_id, case_id, candidate_id, public_id="approval-1", status="pending"
) -> int:
    connection.execute(
        """INSERT INTO external_dataset_sample_import_approvals(public_id, sample_import_id,
        verification_case_id, candidate_id, purpose, requested_record_limit,
        requested_byte_limit, target_fingerprint, status, requested_by_admin_public_id)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (public_id, sample_import_id, case_id, candidate_id, "manual_review", 500,
         20_000_000, "fp-1", status, ADMIN_ID),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_sample_import_approvals WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_file(connection, sample_import_id, public_id="file-1") -> int:
    connection.execute(
        """INSERT INTO external_dataset_sample_files(public_id, sample_import_id,
        original_filename, safe_filename, relative_path) VALUES (?,?,?,?,?)""",
        (public_id, sample_import_id, "data.txt", "data.txt", "original/data.txt"),
    )
    return connection.execute(
        "SELECT id FROM external_dataset_sample_files WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_fresh_database_reaches_schema_35(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 35
    with database_connection(database) as connection:
        assert PHASE35_TABLES <= _existing_tables(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_34_upgrades_to_35_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v34.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V34:
            apply(connection)
        connection.execute(
            """INSERT INTO external_dataset_search_sessions(public_id, session_code,
            requested_by_admin_public_id) VALUES (?,?,?)""",
            ("sess-preexisting", "preexisting-code", ADMIN_ID),
        )
        connection.commit()
    assert current_schema_version(database) == 34

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 35
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE35_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        preserved = connection.execute(
            "SELECT session_code FROM external_dataset_search_sessions WHERE public_id=?",
            ("sess-preexisting",),
        ).fetchone()
        assert preserved["session_code"] == "preexisting-code"

        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        connection.commit()
        row = connection.execute(
            "SELECT status, current_stage FROM external_dataset_sample_imports WHERE id=?",
            (sample_import_id,),
        ).fetchone()
        assert row["status"] == "draft"
        assert row["current_stage"] == "eligibility_check"


def test_sample_import_code_is_unique(tmp_path: Path) -> None:
    database = tmp_path / "unique.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        _insert_sample_import(connection, case_id, candidate_id)
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_imports(public_id, sample_import_code,
                verification_case_id, candidate_id, purpose, selection_method,
                requested_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
                ("sample-2", "SI-sample-1", case_id, candidate_id, "manual_review",
                 "deterministic_first_n", ADMIN_ID),
            )


def test_sample_import_rejects_unknown_status(tmp_path: Path) -> None:
    database = tmp_path / "status.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_imports(public_id, sample_import_code,
                verification_case_id, candidate_id, purpose, selection_method,
                requested_by_admin_public_id, status) VALUES (?,?,?,?,?,?,?,?)""",
                ("sample-bad", "SI-bad", case_id, candidate_id, "manual_review",
                 "deterministic_first_n", ADMIN_ID, "not_a_real_status"),
            )


def test_sample_import_rejects_unknown_purpose(tmp_path: Path) -> None:
    database = tmp_path / "purpose.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_imports(public_id, sample_import_code,
                verification_case_id, candidate_id, purpose, selection_method,
                requested_by_admin_public_id) VALUES (?,?,?,?,?,?,?)""",
                ("sample-bad-purpose", "SI-bad-purpose", case_id, candidate_id, "training",
                 "deterministic_first_n", ADMIN_ID),
            )


def test_approval_rejects_nonpositive_limits(tmp_path: Path) -> None:
    database = tmp_path / "limits.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_import_approvals(public_id,
                sample_import_id, verification_case_id, candidate_id, purpose,
                requested_record_limit, requested_byte_limit, target_fingerprint,
                requested_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?)""",
                ("approval-bad", sample_import_id, case_id, candidate_id, "manual_review",
                 0, 1000, "fp", ADMIN_ID),
            )


def test_approval_is_immutable_once_approved(tmp_path: Path) -> None:
    database = tmp_path / "approval_immutable.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        approval_id = _insert_approval(connection, sample_import_id, case_id, candidate_id)
        connection.execute(
            "UPDATE external_dataset_sample_import_approvals SET status='approved' WHERE id=?",
            (approval_id,),
        )
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE external_dataset_sample_import_approvals SET "
                "approved_record_limit=999 WHERE id=?",
                (approval_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE external_dataset_sample_import_approvals SET target_fingerprint='changed' "
                "WHERE id=?",
                (approval_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE external_dataset_sample_import_approvals SET status='pending' WHERE id=?",
                (approval_id,),
            )


def test_approval_can_transition_from_approved_to_expired_without_touching_bound_fields(
    tmp_path: Path,
) -> None:
    database = tmp_path / "approval_expire.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        approval_id = _insert_approval(connection, sample_import_id, case_id, candidate_id)
        connection.execute(
            "UPDATE external_dataset_sample_import_approvals SET status='approved' WHERE id=?",
            (approval_id,),
        )
        connection.commit()
        connection.execute(
            "UPDATE external_dataset_sample_import_approvals SET status='expired' WHERE id=?",
            (approval_id,),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM external_dataset_sample_import_approvals WHERE id=?",
            (approval_id,),
        ).fetchone()
        assert row["status"] == "expired"


def test_file_rejects_unknown_status_and_blocked_class(tmp_path: Path) -> None:
    database = tmp_path / "file_checks.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_files(public_id, sample_import_id,
                original_filename, safe_filename, relative_path, status)
                VALUES (?,?,?,?,?,?)""",
                ("file-bad", sample_import_id, "x.exe", "x.exe", "original/x.exe", "not_a_status"),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_files(public_id, sample_import_id,
                original_filename, safe_filename, relative_path, blocked_class)
                VALUES (?,?,?,?,?,?)""",
                ("file-bad2", sample_import_id, "x.exe", "x.exe", "original/x.exe",
                 "not_a_real_class"),
            )


def test_record_issue_rejects_unknown_category(tmp_path: Path) -> None:
    database = tmp_path / "issue_checks.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_record_issues(public_id,
                sample_import_id, issue_category, issue_type, status)
                VALUES (?,?,?,?,?)""",
                ("issue-bad", sample_import_id, "not_a_category", "email_address", "possible"),
            )


def test_review_requires_nonempty_reason(tmp_path: Path) -> None:
    database = tmp_path / "review_reason.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_reviews(public_id, sample_import_id,
                target_type, decision, reason, reviewer_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                ("review-bad", sample_import_id, "record", "accept", "   ", ADMIN_ID),
            )


def test_report_rejects_duplicate_version_per_import(tmp_path: Path) -> None:
    database = tmp_path / "report_unique.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        connection.execute(
            """INSERT INTO external_dataset_sample_reports(public_id, sample_import_id,
            report_version, rag_sandbox_eligible, training_assessment_status,
            finalized_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
            ("report-1", sample_import_id, 1, 0, "not_assessed", ADMIN_ID),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_reports(public_id, sample_import_id,
                report_version, rag_sandbox_eligible, training_assessment_status,
                finalized_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
                ("report-2", sample_import_id, 1, 1, "potentially_suitable", ADMIN_ID),
            )


def test_report_rejects_training_approved_as_a_status(tmp_path: Path) -> None:
    database = tmp_path / "report_no_training_approved.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_reports(public_id, sample_import_id,
                report_version, rag_sandbox_eligible, training_assessment_status,
                finalized_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
                ("report-bad", sample_import_id, 1, 1, "training_approved", ADMIN_ID),
            )


def test_deletion_request_requires_nonempty_reason(tmp_path: Path) -> None:
    database = tmp_path / "deletion_reason.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO external_dataset_sample_deletion_requests(public_id,
                deletion_request_code, sample_import_id, reason, requested_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                ("del-bad", "DR-1", sample_import_id, "", ADMIN_ID),
            )


def test_append_only_tables_reject_update_and_delete(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        file_id = _insert_file(connection, sample_import_id)

        connection.execute(
            """INSERT INTO external_dataset_sample_download_events(public_id, sample_import_id,
            file_id, event_type, performed_by_admin_public_id) VALUES (?,?,?,?,?)""",
            ("dl-1", sample_import_id, file_id, "started", ADMIN_ID),
        )
        connection.execute(
            """INSERT INTO external_dataset_sample_extraction_events(public_id,
            sample_import_id, archive_file_id, event_type, performed_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            ("ex-1", sample_import_id, file_id, "started", ADMIN_ID),
        )
        connection.execute(
            """INSERT INTO external_dataset_sample_scan_results(public_id, sample_import_id,
            file_id, verdict) VALUES (?,?,?,?)""",
            ("scan-1", sample_import_id, file_id, "clean_by_policy"),
        )
        connection.execute(
            """INSERT INTO external_dataset_sample_reviews(public_id, sample_import_id,
            target_type, decision, reason, reviewer_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            ("review-1", sample_import_id, "file", "accept", "Looks safe", ADMIN_ID),
        )
        connection.execute(
            """INSERT INTO external_dataset_sample_reports(public_id, sample_import_id,
            report_version, rag_sandbox_eligible, training_assessment_status,
            finalized_by_admin_public_id) VALUES (?,?,?,?,?,?)""",
            ("report-1", sample_import_id, 1, 0, "not_assessed", ADMIN_ID),
        )
        connection.execute(
            """INSERT INTO external_dataset_sample_events(public_id, sample_import_id,
            event_type) VALUES (?,?,?)""",
            ("event-1", sample_import_id, "import_created"),
        )
        connection.execute(
            """INSERT INTO external_dataset_sample_deletion_requests(public_id,
            deletion_request_code, sample_import_id, reason, requested_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            ("del-1", "DR-1", sample_import_id, "No longer needed", ADMIN_ID),
        )
        connection.commit()

        cases = [
            ("external_dataset_sample_download_events", "dl-1", "event_type='completed'"),
            ("external_dataset_sample_extraction_events", "ex-1", "event_type='completed'"),
            ("external_dataset_sample_scan_results", "scan-1", "verdict='blocked'"),
            ("external_dataset_sample_reviews", "review-1", "reason='changed'"),
            ("external_dataset_sample_reports", "report-1", "rag_sandbox_eligible=1"),
            ("external_dataset_sample_events", "event-1", "summary='changed'"),
            ("external_dataset_sample_deletion_requests", "del-1", "status='executed'"),
        ]
        for table, public_id, set_clause in cases:
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(
                    f"UPDATE {table} SET {set_clause} WHERE public_id=?", (public_id,)
                )
            with pytest.raises(sqlite3.IntegrityError):
                connection.execute(f"DELETE FROM {table} WHERE public_id=?", (public_id,))


def test_sample_import_with_child_rows_can_never_be_deleted(tmp_path: Path) -> None:
    # Mirrors Phase 11's own discovery: `ON DELETE CASCADE` still fires
    # the child's own BEFORE DELETE trigger for an implicit cascade, so
    # a sample import that has any append-only child row is
    # structurally undeletable, only ever cancellable/expirable via its
    # own status column.
    database = tmp_path / "cascade.db"
    initialize_database(database)
    with database_connection(database) as connection:
        _session_id, candidate_id, case_id = _setup_case(connection)
        sample_import_id = _insert_sample_import(connection, case_id, candidate_id)
        connection.execute(
            """INSERT INTO external_dataset_sample_events(public_id, sample_import_id,
            event_type) VALUES (?,?,?)""",
            ("event-cascade", sample_import_id, "import_created"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM external_dataset_sample_imports WHERE id = ?", (sample_import_id,)
            )
        remaining = connection.execute(
            "SELECT 1 FROM external_dataset_sample_events WHERE public_id='event-cascade'"
        ).fetchone()
        assert remaining is not None
