import sqlite3
from pathlib import Path

import pytest

from backend.database import migrations as db_migrations
from backend.database.migrations import initialize_database
from backend.database.schema import SCHEMA_VERSION

_INSERT = """INSERT INTO document_sft_candidates(
    public_id, document_source_id, source_page_start, source_page_end, task, instruction,
    response, input_language, output_language, rights_status, generation_method, content_hash
) VALUES (?, 1, 1, 1, 'definition', 'instr', 'resp', 'en', 'en', 'pending', 'template_heuristic_v1', ?)"""


def test_fresh_database_reaches_schema_version_73(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    version = initialize_database(db_path)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 73


def test_new_candidate_defaults_to_not_checked_content_safety_status(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(_INSERT, ("c1", "hash1"))
        connection.commit()
        row = connection.execute(
            "SELECT content_safety_status, content_safety_findings_json, "
            "content_safety_checked_at FROM document_sft_candidates WHERE public_id='c1'"
        ).fetchone()
        assert row == ("not_checked", None, None)
    finally:
        connection.close()


def test_content_safety_columns_are_freely_writable(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(_INSERT, ("c2", "hash2"))
        connection.commit()
        connection.execute(
            "UPDATE document_sft_candidates SET content_safety_status='blocked',"
            "content_safety_findings_json='[\"prompt_injection\"]',"
            "content_safety_checked_at='2026-08-16T00:00:00Z' WHERE public_id='c2'"
        )
        connection.commit()
        row = connection.execute(
            "SELECT content_safety_status, content_safety_findings_json "
            "FROM document_sft_candidates WHERE public_id='c2'"
        ).fetchone()
        assert row == ("blocked", '["prompt_injection"]')
    finally:
        connection.close()


def test_migration_073_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    version_again = initialize_database(db_path)
    assert version_again == SCHEMA_VERSION


def test_no_foreign_key_violations_or_integrity_errors_after_migration_073(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        assert [row[0] for row in connection.execute("PRAGMA integrity_check")] == ["ok"]
    finally:
        connection.close()


def test_upgrade_from_pre_073_database_preserves_existing_rows_and_ids(
    tmp_path: Path,
) -> None:
    """`document_sft_candidates` was introduced by an earlier migration
    (043) whose `CREATE TABLE` text lives in this same schema.py file --
    Phase 2.7B added the three new columns directly to that shared
    definition (matching this table's own existing convention of one
    CREATE TABLE, not a versioned rebuild), so replaying migrations 1-72
    from the *current* schema.py cannot by itself reproduce a genuinely
    pre-fix table shape. Instead, this test builds a `document_sft_
    candidates` table matching the exact pre-Phase-2.7B shape by hand
    (mirroring `initialize_database`'s real production upgrade path: an
    existing table that predates migration 073's three new columns) and
    confirms `_apply_v73` adds them without disturbing existing rows/ids."""

    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("BEGIN")
        connection.execute(
            """CREATE TABLE document_sft_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id TEXT NOT NULL UNIQUE,
                document_source_id INTEGER NOT NULL,
                source_chunk_id INTEGER,
                source_page_start INTEGER NOT NULL,
                source_page_end INTEGER NOT NULL,
                task TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT 'general',
                difficulty TEXT NOT NULL DEFAULT 'basic',
                instruction TEXT NOT NULL,
                context TEXT NOT NULL DEFAULT '',
                response TEXT NOT NULL,
                input_language TEXT NOT NULL,
                output_language TEXT NOT NULL,
                rights_status TEXT NOT NULL,
                quality_status TEXT NOT NULL DEFAULT 'draft',
                generation_method TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                duplicate_of_public_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, name TEXT, "
            "applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.executemany(
            "INSERT INTO schema_migrations(version) VALUES (?)", [(v,) for v in range(1, 73)]
        )
        connection.commit()

        columns_before = {
            row[1] for row in connection.execute("PRAGMA table_info(document_sft_candidates)")
        }
        assert "content_safety_status" not in columns_before

        connection.execute(_INSERT, ("legacy-row", "legacy-hash"))
        connection.commit()
        legacy_row_id = connection.execute(
            "SELECT id FROM document_sft_candidates WHERE public_id='legacy-row'"
        ).fetchone()[0]

        connection.execute("BEGIN")
        db_migrations._apply_v73(connection)
        connection.commit()
    finally:
        connection.close()

    connection = sqlite3.connect(db_path)
    try:
        row = connection.execute(
            "SELECT id, content_safety_status FROM document_sft_candidates "
            "WHERE public_id='legacy-row'"
        ).fetchone()
        assert row == (legacy_row_id, "not_checked")

        connection.execute(_INSERT, ("post-fix-row", "post-fix-hash"))
        connection.commit()
        new_id, new_status = connection.execute(
            "SELECT id, content_safety_status FROM document_sft_candidates "
            "WHERE public_id='post-fix-row'"
        ).fetchone()
        assert new_status == "not_checked"
        assert new_id > legacy_row_id
    finally:
        connection.close()


def test_running_migration_073_twice_on_the_same_connection_does_not_duplicate_columns(
    tmp_path: Path,
) -> None:
    """`_apply_v73` must be safe to invoke twice against an already-current
    database (the same guard every other `_apply_vN` uses) -- exercised
    directly here rather than only through `initialize_database`'s own
    early-return, since that early-return is itself what this test proves
    is unnecessary to rely on."""

    db_path = tmp_path / "fresh.db"
    initialize_database(db_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("BEGIN")
        db_migrations._apply_v73(connection)
        connection.commit()
        columns = [
            row[1] for row in connection.execute("PRAGMA table_info(document_sft_candidates)")
        ]
        assert columns.count("content_safety_status") == 1
    finally:
        connection.close()
