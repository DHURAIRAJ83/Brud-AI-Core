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
    current_schema_version,
    initialize_database,
    upgrade_database,
)
from backend.database.schema import SCHEMA_VERSION

PHASE26_TABLES = {
    "semantic_chunks",
    "semantic_chunk_revisions",
    "semantic_chunk_relations",
    "semantic_chunk_reviews",
    "semantic_chunk_events",
    "structured_record_candidates",
    "structured_record_candidate_chunks",
    "structured_record_candidate_revisions",
    "structured_record_reviews",
}

APPLY_THROUGH_V25 = (
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
)


def _existing_tables(connection) -> set[str]:
    return {
        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _insert_source(connection, public_id: str, code: str) -> int:
    connection.execute(
        """INSERT INTO data_sources(public_id, source_code, title, source_type,
        created_by_admin_public_id) VALUES (?,?,?,?,?)""",
        (public_id, code, "Test source", "document_derived", "admin-1"),
    )
    return connection.execute(
        "SELECT id FROM data_sources WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def _insert_document(connection, public_id: str) -> int:
    connection.execute(
        """INSERT INTO document_sources(
            public_id, original_filename, stored_filename, document_type, mime_type,
            file_size_bytes, checksum_sha256, page_count, extraction_strategy, status,
            created_by_admin_public_id
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            public_id,
            "a.pdf",
            f"{public_id}-stored.pdf",
            "pdf",
            "application/pdf",
            1024,
            f"hash-{public_id}",
            1,
            "auto",
            "review_ready",
            "admin-1",
        ),
    )
    return connection.execute(
        "SELECT id FROM document_sources WHERE public_id=?", (public_id,)
    ).fetchone()[0]


def test_fresh_database_reaches_schema_26(tmp_path: Path) -> None:
    database = tmp_path / "fresh.db"
    initialize_database(database)
    assert current_schema_version(database) == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 26
    with database_connection(database) as connection:
        assert PHASE26_TABLES <= _existing_tables(connection)
        assert connection.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_schema_25_upgrades_to_26_and_preserves_existing_data(tmp_path: Path) -> None:
    database = tmp_path / "v25.db"
    with database_connection(database) as connection:
        for apply in APPLY_THROUGH_V25:
            apply(connection)
        _insert_document(connection, "00000000-0000-0000-0000-000000000d26")
        connection.commit()
    assert current_schema_version(database) == 25

    settings = Settings(
        database_path=database,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
    )
    version, _backup, integrity = upgrade_database(settings)
    assert version == SCHEMA_VERSION
    assert SCHEMA_VERSION >= 26
    assert integrity == "ok"

    with database_connection(database) as connection:
        assert PHASE26_TABLES <= _existing_tables(connection)
        assert not list(connection.execute("PRAGMA foreign_key_check"))
        row = connection.execute(
            "SELECT original_filename FROM document_sources WHERE public_id=?",
            ("00000000-0000-0000-0000-000000000d26",),
        ).fetchone()
        assert row["original_filename"] == "a.pdf"


def test_semantic_chunks_requires_valid_type_and_status(tmp_path: Path) -> None:
    database = tmp_path / "check.db"
    initialize_database(database)
    with database_connection(database) as connection:
        source_id = _insert_source(connection, "src-1", "SRC-1")
        document_id = _insert_document(connection, "doc-1")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO semantic_chunks(public_id, chunk_code, document_source_id,
                data_source_id, chunk_type, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                ("chunk-bad", "CHK-BAD", document_id, source_id, "not_a_real_type", "admin-1"),
            )
        connection.execute(
            """INSERT INTO semantic_chunks(public_id, chunk_code, document_source_id,
            data_source_id, chunk_type, created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            ("chunk-1", "CHK-1", document_id, source_id, "paragraph", "admin-1"),
        )
        connection.commit()
        row = connection.execute(
            "SELECT status FROM semantic_chunks WHERE public_id=?", ("chunk-1",)
        ).fetchone()
        assert row["status"] == "draft"


def test_semantic_chunk_revisions_and_events_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        source_id = _insert_source(connection, "src-2", "SRC-2")
        document_id = _insert_document(connection, "doc-2")
        connection.execute(
            """INSERT INTO semantic_chunks(public_id, chunk_code, document_source_id,
            data_source_id, chunk_type, created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            ("chunk-2", "CHK-2", document_id, source_id, "paragraph", "admin-1"),
        )
        chunk_id = connection.execute(
            "SELECT id FROM semantic_chunks WHERE public_id=?", ("chunk-2",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO semantic_chunk_revisions(public_id, chunk_id, revision_number,
            text, normalized_text, content_hash, created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?)""",
            ("rev-1", chunk_id, 1, "hello", "hello", "hash1", "admin-1"),
        )
        connection.execute(
            """INSERT INTO semantic_chunk_events(public_id, chunk_id, event_type,
            performed_by_admin_public_id) VALUES (?,?,?,?)""",
            ("evt-1", chunk_id, "chunk_created", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE semantic_chunk_revisions SET text='changed' WHERE public_id=?", ("rev-1",)
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM semantic_chunk_events WHERE public_id=?", ("evt-1",))


def test_structured_record_candidate_revisions_are_append_only(tmp_path: Path) -> None:
    database = tmp_path / "structured_append_only.db"
    initialize_database(database)
    with database_connection(database) as connection:
        source_id = _insert_source(connection, "src-3", "SRC-3")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO structured_record_candidates(public_id, candidate_code,
                record_type, data_source_id, created_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                ("cand-bad", "SR-BAD", "not_a_real_type", source_id, "admin-1"),
            )
        connection.execute(
            """INSERT INTO structured_record_candidates(public_id, candidate_code,
            record_type, data_source_id, created_by_admin_public_id)
            VALUES (?,?,?,?,?)""",
            ("cand-1", "SR-1", "dictionary_entry", source_id, "admin-1"),
        )
        candidate_id = connection.execute(
            "SELECT id FROM structured_record_candidates WHERE public_id=?", ("cand-1",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO structured_record_candidate_revisions(public_id, candidate_id,
            revision_number, word, content_hash, created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            ("srev-1", candidate_id, 1, "vanakkam", "hash1", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE structured_record_candidate_revisions SET word='changed' "
                "WHERE public_id=?",
                ("srev-1",),
            )


def test_semantic_chunk_relations_prevent_duplicate_edges(tmp_path: Path) -> None:
    database = tmp_path / "relations.db"
    initialize_database(database)
    with database_connection(database) as connection:
        source_id = _insert_source(connection, "src-4", "SRC-4")
        document_id = _insert_document(connection, "doc-4")
        for code in ("chunk-a", "chunk-b"):
            connection.execute(
                """INSERT INTO semantic_chunks(public_id, chunk_code, document_source_id,
                data_source_id, chunk_type, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                (code, code.upper(), document_id, source_id, "paragraph", "admin-1"),
            )
        parent_id = connection.execute(
            "SELECT id FROM semantic_chunks WHERE public_id=?", ("chunk-a",)
        ).fetchone()[0]
        child_id = connection.execute(
            "SELECT id FROM semantic_chunks WHERE public_id=?", ("chunk-b",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO semantic_chunk_relations(public_id, source_chunk_id, target_chunk_id,
            relationship_type, created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            ("rel-1", child_id, parent_id, "child_of", "admin-1"),
        )
        connection.commit()
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO semantic_chunk_relations(public_id, source_chunk_id,
                target_chunk_id, relationship_type, created_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                ("rel-2", child_id, parent_id, "child_of", "admin-1"),
            )
