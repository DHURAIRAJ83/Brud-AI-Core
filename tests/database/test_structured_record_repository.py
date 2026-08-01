from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.structured_records import (
    StructuredRecordRepository,
    public_row,
)


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "structured.db"
    initialize_database(path)
    return path


@pytest.fixture
def repository(database_path: Path) -> StructuredRecordRepository:
    return StructuredRecordRepository(database_path)


def _make_source(database_path: Path) -> int:
    source_repo = DataSourceRepository(database_path)
    with source_repo.transaction() as connection:
        public_id = source_repo.create_source(
            connection,
            {
                "source_code": "SRC-STRUCT-TEST-0001",
                "title": "Test source",
                "source_type": "document_derived",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with source_repo.transaction() as connection:
        return source_repo.source(connection, public_id)["id"]


def test_create_read_update_candidate(
    repository: StructuredRecordRepository, database_path: Path
) -> None:
    source_id = _make_source(database_path)
    with repository.transaction() as connection:
        public_id = repository.create_candidate(
            connection,
            {
                "candidate_code": "SR-0001",
                "record_type": "dictionary_entry",
                "data_source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        row = public_row(repository.candidate(connection, public_id))
        assert row["candidate_code"] == "SR-0001"
        assert row["status"] == "draft"
        assert "id" not in row
        repository.update_candidate(
            connection,
            repository.candidate(connection, public_id)["id"],
            {"status": "needs_review"},
        )
    with repository.transaction() as connection:
        row = public_row(repository.candidate(connection, public_id))
        assert row["status"] == "needs_review"


def test_create_and_list_revisions_with_typed_fields(
    repository: StructuredRecordRepository, database_path: Path
) -> None:
    source_id = _make_source(database_path)
    with repository.transaction() as connection:
        candidate_public_id = repository.create_candidate(
            connection,
            {
                "candidate_code": "SR-0002",
                "record_type": "dictionary_entry",
                "data_source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )
        candidate_id = repository.candidate(connection, candidate_public_id)["id"]
        repository.create_revision(
            connection,
            {
                "candidate_id": candidate_id,
                "revision_number": 1,
                "word": "vanakkam",
                "part_of_speech": "interjection",
                "meanings_json": '["hello", "greeting"]',
                "content_hash": "hash1",
                "created_by_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        candidate_id = repository.candidate(connection, candidate_public_id)["id"]
        revisions = repository.list_revisions(connection, candidate_id)
        assert len(revisions) == 1
        assert revisions[0]["word"] == "vanakkam"
        assert repository.latest_revision_number(connection, candidate_id) == 1
        assert (
            repository.content_hash_exists(connection, "dictionary_entry", "hash1")
            == candidate_public_id
        )
        assert (
            repository.content_hash_exists(connection, "dictionary_entry", "no-such-hash") is None
        )


def test_list_by_type_returns_active_revision_snapshot(
    repository: StructuredRecordRepository, database_path: Path
) -> None:
    source_id = _make_source(database_path)
    with repository.transaction() as connection:
        candidate_public_id = repository.create_candidate(
            connection,
            {
                "candidate_code": "SR-0003",
                "record_type": "question_answer",
                "data_source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )
        candidate_id = repository.candidate(connection, candidate_public_id)["id"]
        revision_public_id = repository.create_revision(
            connection,
            {
                "candidate_id": candidate_id,
                "revision_number": 1,
                "question": "What is Tamil?",
                "answer": "A Dravidian language.",
                "content_hash": "hash-qa",
                "created_by_admin_public_id": "admin-1",
            },
        )
        revision_id = repository.revision(connection, revision_public_id)["id"]
        repository.update_candidate(connection, candidate_id, {"active_revision_id": revision_id})
    with repository.transaction() as connection:
        entries = repository.list_by_type(connection, "question_answer")
        assert len(entries) == 1
        assert entries[0]["question"] == "What is Tamil?"


def test_link_chunk_and_reviews(
    repository: StructuredRecordRepository, database_path: Path
) -> None:
    from backend.database.repositories.documents import DocumentRepository
    from backend.database.repositories.semantic_chunks import SemanticChunkRepository

    source_id = _make_source(database_path)
    doc_repo = DocumentRepository(database_path)
    with doc_repo.transaction() as connection:
        connection.execute(
            """INSERT INTO document_sources(
                public_id, original_filename, stored_filename, document_type, mime_type,
                file_size_bytes, checksum_sha256, page_count, extraction_strategy, status,
                created_by_admin_public_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "doc-struct-test",
                "a.pdf",
                "a-stored.pdf",
                "pdf",
                "application/pdf",
                1024,
                "hashstructtest",
                1,
                "auto",
                "review_ready",
                "admin-1",
            ),
        )
        document_id = connection.execute(
            "SELECT id FROM document_sources WHERE public_id=?", ("doc-struct-test",)
        ).fetchone()["id"]

    chunk_repo = SemanticChunkRepository(database_path)
    with chunk_repo.transaction() as connection:
        chunk_public_id = chunk_repo.create_chunk(
            connection,
            {
                "chunk_code": "CHK-LINK",
                "document_source_id": document_id,
                "data_source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )

    with repository.transaction() as connection:
        candidate_public_id = repository.create_candidate(
            connection,
            {
                "candidate_code": "SR-0004",
                "record_type": "knowledge_note",
                "data_source_id": source_id,
                "created_by_admin_public_id": "admin-1",
            },
        )
        candidate_id = repository.candidate(connection, candidate_public_id)["id"]
        chunk_id = connection.execute(
            "SELECT id FROM semantic_chunks WHERE public_id=?", (chunk_public_id,)
        ).fetchone()["id"]
        repository.link_chunk(connection, candidate_id, chunk_id)
        revision_public_id = repository.create_revision(
            connection,
            {
                "candidate_id": candidate_id,
                "revision_number": 1,
                "title": "Test note",
                "content_hash": "hash-note",
                "created_by_admin_public_id": "admin-1",
            },
        )
        revision_id = repository.revision(connection, revision_public_id)["id"]
        repository.create_review(
            connection,
            {
                "candidate_id": candidate_id,
                "revision_id": revision_id,
                "review_status": "approved",
                "reviewer_admin_public_id": "admin-1",
            },
        )
    with repository.transaction() as connection:
        candidate_id = repository.candidate(connection, candidate_public_id)["id"]
        linked = repository.list_candidate_chunks(connection, candidate_id)
        assert len(linked) == 1
        assert linked[0]["chunk_public_id"] == chunk_public_id
        assert len(repository.list_reviews(connection, candidate_id)) == 1
