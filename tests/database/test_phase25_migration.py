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
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE25_TABLES = {
    "document_page_extractions",
    "document_page_review_events",
    "document_repeated_elements",
}

APPLY_THROUGH_V24 = (
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
)


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _existing_columns(connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def test_fresh_database_reaches_schema_25(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 25
    with database_connection(database) as connection:
        assert PHASE25_TABLES <= _existing_tables(connection)
        columns = _existing_columns(connection, "document_pages")
        assert {
            "review_status",
            "reviewed_by_admin_public_id",
            "reviewed_at",
            "review_notes",
            "approved_revision_number",
        } <= columns
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_24_upgrades_to_25_and_preserves_existing_documents(tmp_path: Path) -> None:
    database = tmp_path / "v24.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V24:
            apply(connection)
        # A legacy document that predates the review workspace entirely --
        # must survive untouched and must default to review_status='pending'
        # rather than being silently marked as reviewed/approved.
        connection.execute(
            """INSERT INTO document_sources(
                public_id, original_filename, stored_filename, document_type, mime_type,
                file_size_bytes, checksum_sha256, page_count, extraction_strategy, status,
                created_by_admin_public_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "00000000-0000-0000-0000-000000000d25",
                "legacy.pdf",
                "legacy-stored.pdf",
                "pdf",
                "application/pdf",
                1024,
                "legacyhash",
                1,
                "auto",
                "completed",
                "legacy-admin",
            ),
        )
        document_id = connection.execute(
            "SELECT id FROM document_sources WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000d25",),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO document_pages(public_id, document_source_id, page_number, "
            "raw_text, cleaned_text) VALUES (?,?,?,?,?)",
            ("legacy-page-1", document_id, 1, "raw legacy text", "cleaned legacy text"),
        )
        connection.commit()
    assert current_schema_version(database) == 24

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 25
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE25_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        row = connection.execute(
            "SELECT original_filename, status FROM document_sources WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000d25",),
        ).fetchone()
        assert row["original_filename"] == "legacy.pdf"
        assert row["status"] == "completed"
        page_row = connection.execute(
            "SELECT raw_text, cleaned_text, review_status FROM document_pages WHERE public_id=?",
            ("legacy-page-1",),
        ).fetchone()
        assert page_row["raw_text"] == "raw legacy text"
        assert page_row["cleaned_text"] == "cleaned legacy text"
        assert page_row["review_status"] == "pending"


def test_document_page_extractions_requires_valid_method(tmp_path: Path) -> None:
    database = tmp_path / "check.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO document_sources(
                public_id, original_filename, stored_filename, document_type, mime_type,
                file_size_bytes, checksum_sha256, page_count, extraction_strategy, status,
                created_by_admin_public_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "doc-1",
                "a.pdf",
                "a-stored.pdf",
                "pdf",
                "application/pdf",
                1024,
                "hash1",
                1,
                "auto",
                "ready",
                "admin-1",
            ),
        )
        document_id = connection.execute(
            "SELECT id FROM document_sources WHERE public_id=?", ("doc-1",)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO document_pages(public_id, document_source_id, page_number) VALUES (?,?,?)",
            ("page-1", document_id, 1),
        )
        page_id = connection.execute(
            "SELECT id FROM document_pages WHERE public_id=?", ("page-1",)
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO document_page_extractions(public_id, document_page_id, "
                "extraction_method, created_by_admin_public_id) VALUES (?,?,?,?)",
                ("ext-bad", page_id, "not_a_real_method", "admin-1"),
            )


def test_document_page_extractions_and_review_events_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO document_sources(
                public_id, original_filename, stored_filename, document_type, mime_type,
                file_size_bytes, checksum_sha256, page_count, extraction_strategy, status,
                created_by_admin_public_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "doc-2",
                "b.pdf",
                "b-stored.pdf",
                "pdf",
                "application/pdf",
                1024,
                "hash2",
                1,
                "auto",
                "ready",
                "admin-1",
            ),
        )
        document_id = connection.execute(
            "SELECT id FROM document_sources WHERE public_id=?", ("doc-2",)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO document_pages(public_id, document_source_id, page_number) VALUES (?,?,?)",
            ("page-2", document_id, 1),
        )
        page_id = connection.execute(
            "SELECT id FROM document_pages WHERE public_id=?", ("page-2",)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO document_page_extractions(public_id, document_page_id, "
            "extraction_method, raw_text, created_by_admin_public_id) VALUES (?,?,?,?,?)",
            ("ext-1", page_id, "embedded", "hello", "admin-1"),
        )
        connection.execute(
            "INSERT INTO document_page_review_events(public_id, document_page_id, action, "
            "review_status_after, performed_by_admin_public_id) VALUES (?,?,?,?,?)",
            ("evt-1", page_id, "approve", "approved", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE document_page_extractions SET raw_text='changed' WHERE public_id=?",
                ("ext-1",),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM document_page_review_events WHERE public_id=?", ("evt-1",)
            )


def test_document_repeated_elements_requires_valid_confidence(tmp_path: Path) -> None:
    database = tmp_path / "repeated.db"
    initialize_database(database)
    with database_connection(database) as connection:
        connection.execute(
            """INSERT INTO document_sources(
                public_id, original_filename, stored_filename, document_type, mime_type,
                file_size_bytes, checksum_sha256, page_count, extraction_strategy, status,
                created_by_admin_public_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "doc-3",
                "c.pdf",
                "c-stored.pdf",
                "pdf",
                "application/pdf",
                1024,
                "hash3",
                3,
                "auto",
                "ready",
                "admin-1",
            ),
        )
        document_id = connection.execute(
            "SELECT id FROM document_sources WHERE public_id=?", ("doc-3",)
        ).fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO document_repeated_elements(public_id, document_source_id, "
                "normalized_text, element_type, confidence) VALUES (?,?,?,?,?)",
                ("rep-bad", document_id, "page 1", "header", 1.5),
            )
        connection.execute(
            "INSERT INTO document_repeated_elements(public_id, document_source_id, "
            "normalized_text, element_type, confidence) VALUES (?,?,?,?,?)",
            ("rep-1", document_id, "confidential draft", "header", 0.9),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM document_repeated_elements WHERE public_id=?", ("rep-1",)
        ).fetchone()
        assert row["status"] == "suggested"
