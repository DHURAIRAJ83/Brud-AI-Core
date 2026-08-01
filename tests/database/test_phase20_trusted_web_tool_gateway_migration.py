"""Phase 20 -- migration 042 (Trusted Web / Deterministic Tool gateway)
schema tests: fresh/upgrade paths, table existence, append-only
enforcement, no raw page body or secret columns, clean FK check,
idempotency."""

import sqlite3
from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.schema import SCHEMA_VERSION

_PHASE20_TABLES = (
    "trusted_web_search_events",
    "trusted_web_source_evidence",
    "trusted_web_fetch_events",
    "trusted_web_policy_events",
    "deterministic_tool_execution_events",
    "knowledge_gap_capability_resolutions",
)

_APPEND_ONLY_TABLES = _PHASE20_TABLES  # every Phase 20 table is append-only

_FORBIDDEN_COLUMN_SUBSTRINGS = (
    "raw_body", "page_body", "full_content", "raw_page", "api_key", "password", "secret",
)


def test_fresh_database_reaches_schema_version_42(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 42


def test_upgrade_from_schema_41_reaches_42(tmp_path: Path) -> None:
    db_path = tmp_path / "upgrade.db"
    from backend.database import migrations as migrations_module

    with sqlite3.connect(db_path) as connection:
        connection.execute("BEGIN")
        for version_number in range(1, 42):
            apply_fn = getattr(migrations_module, f"_apply_v{version_number}")
            apply_fn(connection)
        connection.commit()
    assert migrations_module.current_schema_version(db_path) == 41

    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION
    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='trusted_web_search_events'"
        ).fetchone()
        assert row is not None
    finally:
        connection.close()


@pytest.mark.parametrize("table", _PHASE20_TABLES)
def test_all_six_phase20_tables_exist(tmp_path: Path, table: str) -> None:
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


def test_no_raw_page_body_or_secret_columns_anywhere(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        for table in _PHASE20_TABLES:
            columns = {row[1].lower() for row in connection.execute(f"PRAGMA table_info({table})")}
            for forbidden in _FORBIDDEN_COLUMN_SUBSTRINGS:
                matching = {c for c in columns if forbidden in c}
                assert not matching, f"{table} has forbidden column(s): {matching}"
    finally:
        connection.close()


def test_source_evidence_excerpt_is_bounded_text_not_full_body(tmp_path: Path) -> None:
    """`excerpt_redacted` exists (a short, privacy-scanned excerpt) but
    there is no separate raw/full page-content column alongside it."""

    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(trusted_web_source_evidence)")
        }
        assert "excerpt_redacted" in columns
        assert "content_hash" in columns
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


def test_integrity_check_passes_after_migration(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        result = connection.execute("PRAGMA integrity_check").fetchall()
        assert result == [("ok",)]
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
            """INSERT INTO trusted_web_search_events(
                public_id, request_id, query_hash, web_category, provider_name, policy_version,
                status, result_count, conflict_status, overall_freshness_status, latency_ms
            ) VALUES ('se-1','r1','h1','current_general_information','wikipedia','v1','success',
                1,'no_conflict','fresh',10)"""
        )
        search_event_id = connection.execute(
            "SELECT id FROM trusted_web_search_events WHERE public_id='se-1'"
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO knowledge_gap_cases(public_id, event_type, primary_reason_code,
            input_hash) VALUES ('case-1','tool_capability_gap','tool_unsupported_operation','h1')"""
        )
        case_id = connection.execute(
            "SELECT id FROM knowledge_gap_cases WHERE public_id='case-1'"
        ).fetchone()[0]

        inserts = {
            "trusted_web_search_events": None,  # already inserted above
            "trusted_web_source_evidence": (
                "INSERT INTO trusted_web_source_evidence(public_id, search_event_id, "
                "source_url_normalized, source_domain, trust_level, verification_level, "
                "freshness_status, support_status, content_hash, retrieved_at) VALUES "
                "('ev-1', ?, 'https://a.gov/x', 'a.gov', 'official', 'content_verified', "
                "'fresh', 'directly_supports', 'h1', '2026-07-30T00:00:00Z')",
                (search_event_id,),
            ),
            "trusted_web_fetch_events": (
                "INSERT INTO trusted_web_fetch_events(public_id, search_event_id, url_domain, "
                "outcome) VALUES ('fe-1', ?, 'a.gov', 'success')",
                (search_event_id,),
            ),
            "trusted_web_policy_events": (
                "INSERT INTO trusted_web_policy_events(public_id, event_type) "
                "VALUES ('pe-1', 'loaded')",
                (),
            ),
            "deterministic_tool_execution_events": (
                "INSERT INTO deterministic_tool_execution_events(public_id, request_id, "
                "tool_name, tool_version, status) VALUES ('te-1', 'r1', 'calculator', 'v1', "
                "'success')",
                (),
            ),
            "knowledge_gap_capability_resolutions": (
                "INSERT INTO knowledge_gap_capability_resolutions(public_id, case_id, "
                "resolution_kind, search_event_id, matched_by) VALUES "
                "('cr-1', ?, 'resolved_by_trusted_web', ?, 'canonical_question_same_case')",
                (case_id, search_event_id),
            ),
        }
        if table != "trusted_web_search_events":
            sql, params = inserts[table]
            connection.execute(sql, params)
        connection.commit()

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(f"UPDATE {table} SET public_id = public_id")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(f"DELETE FROM {table}")
    finally:
        connection.close()
