import sqlite3
from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.schema import SCHEMA_VERSION

_KNOWLEDGE_GAP_TABLES = (
    "knowledge_gap_cases",
    "knowledge_gap_occurrences",
    "knowledge_gap_clusters",
    "knowledge_gap_cluster_members",
    "knowledge_gap_reviews",
    "knowledge_gap_research_notes",
    "knowledge_gap_resolution_events",
    "knowledge_gap_status_events",
    "knowledge_gap_deletion_requests",
    "knowledge_gap_daily_reports",
)

_APPEND_ONLY_TABLES = (
    "knowledge_gap_occurrences",
    "knowledge_gap_cluster_members",
    "knowledge_gap_reviews",
    "knowledge_gap_research_notes",
    "knowledge_gap_resolution_events",
    "knowledge_gap_status_events",
    "knowledge_gap_deletion_requests",
    "knowledge_gap_daily_reports",
)


def test_fresh_database_reaches_schema_version_41(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 41


def test_upgrade_from_schema_40_reaches_41(tmp_path: Path) -> None:
    db_path = tmp_path / "upgrade.db"
    from backend.database import migrations as migrations_module

    with sqlite3.connect(db_path) as connection:
        connection.execute("BEGIN")
        for version_number in range(1, 41):
            apply_fn = getattr(migrations_module, f"_apply_v{version_number}")
            apply_fn(connection)
        connection.commit()
    assert migrations_module.current_schema_version(db_path) == 40

    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_gap_cases'"
        ).fetchone()
        assert row is not None
    finally:
        connection.close()


@pytest.mark.parametrize("table", _KNOWLEDGE_GAP_TABLES)
def test_all_ten_knowledge_gap_tables_exist(tmp_path: Path, table: str) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
        ).fetchone()
        assert row is not None, f"missing table: {table}"
    finally:
        connection.close()


def test_knowledge_gap_cases_has_separate_status_and_stage_columns(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(knowledge_gap_cases)")}
        assert "status" in columns
        assert "stage" in columns
        assert "resolved" not in columns
    finally:
        connection.close()


def test_no_raw_message_columns_anywhere_in_the_registry(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        for table in _KNOWLEDGE_GAP_TABLES:
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            assert "raw_message" not in columns
            assert "raw_question" not in columns
            assert "raw_answer" not in columns
            assert "message" not in columns
            assert "reply" not in columns
    finally:
        connection.close()


def test_no_foreign_key_violations_after_migration(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        assert violations == []
    finally:
        connection.close()


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    version_again = initialize_database(db_path)
    assert version_again == SCHEMA_VERSION


@pytest.mark.parametrize("table", _APPEND_ONLY_TABLES)
def test_append_only_tables_reject_update_and_delete(tmp_path: Path, table: str) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """INSERT INTO knowledge_gap_cases(public_id, event_type, primary_reason_code,
            input_hash) VALUES ('case-1','knowledge_gap','model_knowledge_missing','h1')"""
        )
        case_id = connection.execute(
            "SELECT id FROM knowledge_gap_cases WHERE public_id='case-1'"
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO knowledge_gap_clusters(public_id, canonical_question, primary_language)
            VALUES ('cluster-1','q','ta')"""
        )
        cluster_id = connection.execute(
            "SELECT id FROM knowledge_gap_clusters WHERE public_id='cluster-1'"
        ).fetchone()[0]

        inserts = {
            "knowledge_gap_occurrences": (
                "INSERT INTO knowledge_gap_occurrences(public_id, case_id, request_hash, "
                "event_type) VALUES ('row-1', ?, 'h1', 'knowledge_gap')",
                (case_id,),
            ),
            "knowledge_gap_cluster_members": (
                "INSERT INTO knowledge_gap_cluster_members(public_id, cluster_id, case_id, "
                "decision) VALUES ('row-1', ?, ?, 'same_case')",
                (cluster_id, case_id),
            ),
            "knowledge_gap_reviews": (
                "INSERT INTO knowledge_gap_reviews(public_id, case_id, decision, "
                "reviewed_by_admin_public_id) VALUES ('row-1', ?, 'confirm_gap', 'admin-1')",
                (case_id,),
            ),
            "knowledge_gap_research_notes": (
                "INSERT INTO knowledge_gap_research_notes(public_id, case_id, note_type, "
                "note_text_redacted, author_admin_id) "
                "VALUES ('row-1', ?, 'investigation', 'note', 'admin-1')",
                (case_id,),
            ),
            "knowledge_gap_resolution_events": (
                "INSERT INTO knowledge_gap_resolution_events(public_id, case_id, "
                "resolution_type, resolved_by_admin_public_id) "
                "VALUES ('row-1', ?, 'not_reproducible', 'admin-1')",
                (case_id,),
            ),
            "knowledge_gap_status_events": (
                "INSERT INTO knowledge_gap_status_events(public_id, case_id, to_status, "
                "to_stage, changed_by) VALUES ('row-1', ?, 'new', 'capture', 'system')",
                (case_id,),
            ),
            "knowledge_gap_deletion_requests": (
                "INSERT INTO knowledge_gap_deletion_requests(public_id, case_id, state, "
                "requested_by_admin_public_id) VALUES ('row-1', ?, 'requested', 'admin-1')",
                (case_id,),
            ),
            "knowledge_gap_daily_reports": (
                "INSERT INTO knowledge_gap_daily_reports(public_id, report_date, summary_json) "
                "VALUES ('row-1', '2026-07-30', '{}')",
                (),
            ),
        }
        query, params = inserts[table]
        connection.execute(query, params)
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(f"UPDATE {table} SET public_id = 'changed' WHERE public_id='row-1'")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(f"DELETE FROM {table} WHERE public_id='row-1'")
    finally:
        connection.close()


def test_knowledge_gap_cases_and_clusters_are_mutable(tmp_path: Path) -> None:
    """The two case/cluster tables are the deliberate exception -- they
    transition only through governed repository/service methods, but at
    the schema level they must remain plain, updatable tables (no
    append-only trigger), unlike the other eight."""

    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """INSERT INTO knowledge_gap_cases(public_id, event_type, primary_reason_code,
            input_hash) VALUES ('case-1','knowledge_gap','model_knowledge_missing','h1')"""
        )
        connection.execute(
            "UPDATE knowledge_gap_cases SET status='classified' WHERE public_id='case-1'"
        )
        connection.commit()
        status = connection.execute(
            "SELECT status FROM knowledge_gap_cases WHERE public_id='case-1'"
        ).fetchone()[0]
        assert status == "classified"
    finally:
        connection.close()


def test_case_event_type_check_constraint_rejects_unknown_value(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO knowledge_gap_cases(public_id, event_type, primary_reason_code,
                input_hash) VALUES ('bad','not_a_real_type','x','h1')"""
            )
    finally:
        connection.close()


def test_case_status_check_constraint_rejects_unknown_value(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO knowledge_gap_cases(public_id, event_type, primary_reason_code,
                input_hash, status) VALUES ('bad','knowledge_gap','x','h1','not_a_real_status')"""
            )
    finally:
        connection.close()
